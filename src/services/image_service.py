# -*- coding: utf-8 -*-
"""图片处理服务 - 提取、下载、OCR、缓存管理"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import re
import hashlib
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger
import requests

from services.llm.base import BaseLLMClient


@dataclass
class ImageInfo:
    """图片信息"""
    url: str
    local_path: Optional[str]
    ocr_text: str
    index: int


@dataclass
class ImageProcessResult:
    """图片处理结果"""
    images: List[ImageInfo] = field(default_factory=list)
    ocr_sections: List[str] = field(default_factory=list)  # OCR 结果段落


class ImageService:
    """图片处理服务
    
    职责：
    - 从文本提取图片 URL
    - 下载图片到本地
    - OCR 识别
    - 缓存管理
    """
    
    def __init__(self, ocr_client: BaseLLMClient = None, 
                 max_workers: int = 4,
                 download_timeout: int = 30,
                 ocr_max_retries: int = 2,
                 ocr_min_length: int = 10):
        """初始化图片处理服务
        
        Args:
            ocr_client: OCR 客户端（可选）
            max_workers: 并发处理数量
            download_timeout: 下载超时时间（秒）
            ocr_max_retries: OCR 最大重试次数
            ocr_min_length: OCR 结果最小长度
        """
        self.ocr_client = ocr_client
        self.max_workers = max_workers
        self.download_timeout = download_timeout
        self.ocr_max_retries = ocr_max_retries
        self.ocr_min_length = ocr_min_length
    
    def extract_image_urls(self, text: str) -> List[str]:
        """从文本中提取图片 URL
        
        支持标准 Markdown 图片语法：![alt](url) 或 [image](url)
        
        Args:
            text: 待提取的文本
            
        Returns:
            图片 URL 列表
        """
        pattern = r'!?\[(?:[^\]]*)\]\((https?://[^\)]+)\)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        logger.debug(f"提取到 {len(matches)} 个图片 URL")
        return matches
    
    def download_image(self, url: str, save_dir: Path) -> Path:
        """下载图片到本地
        
        Args:
            url: 图片 URL
            save_dir: 保存目录
            
        Returns:
            本地图片路径
            
        Raises:
            Exception: 下载失败
        """
        # 创建保存目录
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名（使用 URL 的 hash + 扩展名）
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        parsed_url = urlparse(url)
        ext = Path(parsed_url.path).suffix or '.png'
        filename = f"image_{url_hash}{ext}"
        local_path = save_dir / filename
        
        # 如果已下载，直接返回
        if local_path.exists():
            logger.debug(f"图片已存在: {filename}")
            return local_path
        
        # 下载图片
        logger.debug(f"下载图片: {url}")
        response = requests.get(url, timeout=self.download_timeout)
        response.raise_for_status()
        
        # 保存
        local_path.write_bytes(response.content)
        logger.info(f"图片已保存: {filename} ({len(response.content)} 字节)")
        
        return local_path
    
    def _get_ocr_cache_path(self, workspace_dir: Path, img_url: str) -> Path:
        """获取 OCR 缓存文件路径"""
        url_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
        return workspace_dir / f"ocr_cache_{url_hash}.txt"
    
    def _load_ocr_cache(self, workspace_dir: Path, img_url: str) -> Optional[str]:
        """加载缓存的 OCR 结果"""
        cache_file = self._get_ocr_cache_path(workspace_dir, img_url)
        if cache_file.exists():
            return cache_file.read_text(encoding='utf-8')
        return None
    
    def _save_ocr_cache(self, workspace_dir: Path, img_url: str, result: str):
        """保存 OCR 结果到缓存"""
        cache_file = self._get_ocr_cache_path(workspace_dir, img_url)
        cache_file.write_text(result, encoding='utf-8')
    
    def ocr_image(self, url: str, problem_id: str, image_idx: int) -> str:
        """OCR 识别图片
        
        Args:
            url: 图片 URL
            problem_id: 题目 ID（用于日志）
            image_idx: 图片索引
            
        Returns:
            OCR 识别文本
        """
        if not self.ocr_client:
            logger.warning(f"[{problem_id}] 未提供 OCR 客户端，跳过图片 {image_idx}")
            return "[未启用 OCR]"
        
        for attempt in range(1, self.ocr_max_retries + 1):
            try:
                logger.info(f"[{problem_id}] OCR 识别图片 {image_idx} (尝试 {attempt}/{self.ocr_max_retries})")
                ocr_text = self.ocr_client.ocr_image(url)
                logger.info(f"[{problem_id}] OCR 结果长度: {len(ocr_text)}")
                
                # 检查 OCR 结果质量
                if len(ocr_text.strip()) < self.ocr_min_length:
                    logger.warning(f"[{problem_id}] OCR 结果过短 ({len(ocr_text)} 字符)")
                    if attempt < self.ocr_max_retries:
                        continue
                    else:
                        logger.warning(f"[{problem_id}] OCR 重试 {self.ocr_max_retries} 次后仍过短，使用现有结果")
                
                return ocr_text
            except Exception as e:
                logger.error(f"[{problem_id}] OCR 图片 {image_idx} 失败 (尝试 {attempt}/{self.ocr_max_retries}): {e}")
                if attempt >= self.ocr_max_retries:
                    return f"[OCR 失败: {e}]"
        
        return "[OCR 失败]"
    
    def process_images_in_text(self, text: str, workspace_dir: Path, problem_id: str) -> ImageProcessResult:
        """处理文本中的所有图片
        
        完整流程：
        1. 提取图片 URL
        2. 下载图片到本地
        3. OCR 识别（如果启用）
        4. 缓存管理
        
        Args:
            text: 包含图片的文本
            workspace_dir: 工作区目录
            problem_id: 题目 ID（用于日志）
            
        Returns:
            ImageProcessResult 包含图片信息和 OCR 结果
        """
        result = ImageProcessResult()
        
        # 提取图片 URL
        image_urls = self.extract_image_urls(text)
        logger.info(f"[{problem_id}] 检测到 {len(image_urls)} 张图片")
        
        if not image_urls:
            return result
        
        # 如果没有 OCR 客户端，仅下载图片
        if not self.ocr_client:
            logger.warning(f"[{problem_id}] 未提供 OCR 客户端，仅下载图片")
            images_dir = workspace_dir / "images"
            for idx, url in enumerate(image_urls, 1):
                try:
                    local_path = self.download_image(url, images_dir)
                    result.images.append(ImageInfo(
                        url=url,
                        local_path=str(local_path.relative_to(workspace_dir)),
                        ocr_text="[未启用 OCR]",
                        index=idx
                    ))
                except Exception as e:
                    logger.warning(f"[{problem_id}] 下载图片 {idx} 失败: {e}")
                    result.images.append(ImageInfo(
                        url=url,
                        local_path=None,
                        ocr_text=f"[下载失败: {e}]",
                        index=idx
                    ))
            return result
        
        # 并发处理图片（下载 + OCR）
        logger.info(f"[{problem_id}] 开始并发处理图片（下载 + OCR）...")
        images_dir = workspace_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        def process_single_image(idx_url_pair):
            idx, img_url = idx_url_pair
            
            # 下载图片
            local_path = None
            try:
                local_path = self.download_image(img_url, images_dir)
            except Exception as e:
                logger.warning(f"[{problem_id}] 下载图片 {idx} 失败: {e}")
            
            # 尝试从缓存加载 OCR 结果
            cached_ocr = self._load_ocr_cache(workspace_dir, img_url)
            if cached_ocr:
                logger.info(f"[{problem_id}] 使用缓存的 OCR 结果 {idx}")
                return idx, img_url, local_path, cached_ocr
            
            # 执行 OCR
            ocr_text = self.ocr_image(img_url, problem_id, idx)
            
            # 保存到缓存
            if ocr_text and not ocr_text.startswith("["):
                self._save_ocr_cache(workspace_dir, img_url, ocr_text)
            
            return idx, img_url, local_path, ocr_text
        
        # 并发执行
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(image_urls))) as executor:
            futures = {executor.submit(process_single_image, (idx, url)): idx 
                      for idx, url in enumerate(image_urls, 1)}
            
            result_dict = {}
            for future in as_completed(futures):
                try:
                    idx, url, local_path, ocr_text = future.result()
                    result_dict[idx] = (url, local_path, ocr_text)
                except Exception as e:
                    idx = futures[future]
                    logger.error(f"[{problem_id}] 处理图片 {idx} 失败: {e}")
                    result_dict[idx] = (
                        image_urls[idx-1] if idx <= len(image_urls) else "",
                        None,
                        f"[处理失败: {e}]"
                    )
        
        # 按顺序构建结果
        for idx in sorted(result_dict.keys()):
            url, local_path, ocr_text = result_dict[idx]
            
            # 添加图片信息
            result.images.append(ImageInfo(
                url=url,
                local_path=str(local_path.relative_to(workspace_dir)) if local_path else None,
                ocr_text=ocr_text,
                index=idx
            ))
            
            # 添加 OCR 结果段落
            result.ocr_sections.append(f"\n### 图片 {idx} OCR 结果\n{ocr_text}\n")
        
        logger.info(f"[{problem_id}] 图片处理完成：{len(result.images)} 张")
        return result

