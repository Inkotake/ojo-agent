# -*- coding: utf-8 -*-
"""硅基流动 LLM客户端实现（主要用于OCR）"""

from __future__ import annotations

import base64
import io
from typing import Tuple, Optional, Callable

import requests
from loguru import logger

from .base import BaseLLMClient


class SiliconFlowClient(BaseLLMClient):
    """硅基流动API客户端（支持DeepSeek-OCR等模型）"""
    
    def __init__(self, api_key: str, timeout: int = 60, proxies: dict | None = None,
                 verify_ssl: bool = True, model: str = "deepseek-ai/DeepSeek-OCR", 
                 base_url: str = "https://api.siliconflow.cn/v1", **kwargs):
        super().__init__(api_key, timeout, proxies, verify_ssl, model=model, **kwargs)
        self.base_url = base_url
        self.default_model = model
    
    def chat_completion(self, prompt: str, model: str = None, max_tokens: int = 16384,
                       temperature: float = 0.7, top_p: float = 0.9,
                       stream: bool = False, on_chunk: Optional[Callable] = None,
                       system_prompt: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """调用硅基流动API"""
        model = model or self.default_model
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens
        }
        
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
                proxies=self.proxies,
                verify=self.verify_ssl
            )
            r.raise_for_status()
            data = r.json()
            choice = data["choices"][0]["message"]
            return choice.get("content", "") or "", None
        except Exception as e:
            logger.error(f"硅基流动API调用失败: {e}")
            raise
    
    def supports_vision(self) -> bool:
        """硅基流动支持视觉模型（如DeepSeek-OCR）"""
        return True
    
    def ocr_image(self, image_url: str, prompt: Optional[str] = None) -> str:
        """使用DeepSeek OCR识别图片（硅基流动API）"""
        try:
            # 获取system prompt和extraction prompt
            from services.prompt_manager import get_prompt_manager
            pm = get_prompt_manager()
            
            system_prompt = pm.get_ocr_system_prompt()
            if prompt is None:
                prompt = pm.get_ocr_extraction_prompt()
            
            # 如果是HTTP URL，先下载图片转为data URL
            if image_url.startswith("http://") or image_url.startswith("https://"):
                image_url = self._download_and_convert_image(image_url)
            
            # 构建消息（按照OpenAI Vision API格式，SiliconFlow兼容）
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "high"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
            
            logger.debug(f"OCR请求payload: model={self.default_model}, messages={len(messages)}条")
            
            payload = {
                "model": self.default_model,
                "messages": messages,
                "max_tokens": 16000,
                "temperature": 0.2,
                "top_p": 0.8,
                "stream": False
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
                proxies=self.proxies,
                verify=self.verify_ssl
            )
            
            r.raise_for_status()
            data = r.json()
            
            # 详细调试
            logger.debug(f"OCR API响应状态码: {r.status_code}")
            logger.debug(f"OCR API响应data结构: {list(data.keys())}")
            
            if "choices" not in data or not data["choices"]:
                logger.error(f"OCR API响应缺少choices: {data}")
                return f"[OCR响应格式错误: 缺少choices]"
            
            choice = data["choices"][0]["message"]
            content = choice.get("content", "") or ""
            
            logger.debug(f"OCR返回内容长度: {len(content)}")
            if content:
                logger.debug(f"OCR返回内容前200字符: {content[:200]}")
            
            if len(content) < 50:
                logger.warning(f"OCR返回内容过短({len(content)}字符): '{content}'")
                logger.warning(f"完整API响应: {data}")
                logger.warning(f"使用的模型: {self.default_model}")
                logger.warning(f"API endpoint: {self.base_url}")
            
            return content
        
        except Exception as e:
            logger.error(f"OCR识别失败: {e}")
            logger.exception(f"OCR异常详情:")
            return f"[OCR识别失败: {e}]"
    
    def _download_and_convert_image(self, image_url: str) -> str:
        """下载图片并转换为base64 data URL"""
        try:
            logger.debug(f"下载图片: {image_url}")
            r = requests.get(image_url, timeout=30, proxies=self.proxies, verify=self.verify_ssl)
            r.raise_for_status()
            
            logger.debug(f"图片下载成功，大小: {len(r.content)} 字节，Content-Type: {r.headers.get('Content-Type')}")
            
            # 转换为WebP格式的base64（体积更小）
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(r.content))
                logger.debug(f"图片格式: {img.format}, 尺寸: {img.size}, 模式: {img.mode}")
                
                buf = io.BytesIO()
                img.save(buf, format="WEBP", quality=85)
                webp_size = len(buf.getvalue())
                logger.debug(f"转换为WEBP后大小: {webp_size} 字节")
                
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                data_url = f"data:image/webp;base64,{b64}"
                logger.debug(f"Base64编码后长度: {len(b64)} 字符")
            except ImportError:
                # 如果没有PIL，直接使用原始格式
                logger.warning("PIL未安装，使用原始图片格式")
                b64 = base64.b64encode(r.content).decode("utf-8")
                content_type = r.headers.get('Content-Type', 'image/png')
                data_url = f"data:{content_type};base64,{b64}"
                logger.debug(f"使用原始格式，Base64长度: {len(b64)} 字符")
            
            # 检查data URL长度是否合理（不应该太短）
            if len(data_url) < 1000:
                logger.warning(f"data URL过短({len(data_url)}字符)，可能转换失败")
            
            return data_url
        
        except Exception as e:
            logger.error(f"下载并转换图片失败: {e}")
            raise
    
    def get_model_name(self) -> str:
        return self.default_model

