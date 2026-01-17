# -*- coding: utf-8 -*-
"""手动题面格式化服务"""

from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from loguru import logger

from services.llm.factory import LLMFactory
from services.unified_config import AppConfig
from utils.text import sanitize_filename


class ManualProblemFormatter:
    """手动题面格式化器
    
    将用户粘贴的题面文本格式化为标准的problem_data.json格式
    """
    
    def __init__(self, config: AppConfig, llm_factory: Optional[LLMFactory] = None):
        self.config = config
        self.llm_factory = llm_factory or LLMFactory(config)
        # 支持环境变量
        import os
        workspace_base = os.getenv("OJO_WORKSPACE")
        if not workspace_base:
            docker_workspace = Path("/app/workspace")
            if docker_workspace.exists():
                workspace_base = str(docker_workspace)
            else:
                workspace_base = "workspace"
        self.workspace_dir = Path(workspace_base)
        self.cache_dir = self.workspace_dir / ".manual_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_prompts()
    
    def _load_prompts(self):
        """加载prompt配置"""
        try:
            prompts_path = Path("src/services/data/prompts.json")
            if prompts_path.exists():
                with open(prompts_path, 'r', encoding='utf-8') as f:
                    prompts = json.load(f)
                    config = prompts.get("manual_problem_parse", {})
                    self.system_prompt = config.get("system_prompt", "")
                    self.task_instructions = config.get("task_instructions", "")
            else:
                # Fallback
                self.system_prompt = "你是ACM/ICPC题面结构化助手。"
                self.task_instructions = "提取题面结构化信息为JSON"
        except Exception as e:
            logger.warning(f"加载prompts配置失败: {e}")
            self.system_prompt = "你是ACM/ICPC题面结构化助手。"
            self.task_instructions = "提取题面结构化信息为JSON"
    
    def format_problem(self, raw_text: str) -> Dict[str, Any]:
        """格式化题面文本
        
        Args:
            raw_text: 原始题面文本
            
        Returns:
            格式化的题目数据（problem_data.json格式）
            
        Raises:
            RuntimeError: 格式化失败
        """
        # 检查缓存
        cache_key = self._compute_cache_key(raw_text)
        cached = self._load_from_cache(cache_key)
        if cached:
            logger.info("使用缓存的格式化结果")
            return cached
        
        # 调用LLM格式化
        logger.info("开始调用LLM格式化题面...")
        try:
            # 使用gemini作为格式化provider（快速且便宜）
            llm = self.llm_factory.create("gemini", task_type="summary")
            
            # 构建完整的prompt
            full_prompt = f"{self.task_instructions}\n\n题面文本：\n{raw_text}"
            
            response, _ = llm.chat_completion(
                prompt=full_prompt,
                system_prompt=self.system_prompt,
                temperature=0.3,
                max_tokens=4000,
                stream=False
            )
            
            # 提取JSON（去掉可能的markdown代码块）
            json_text = self._extract_json(response)
            logger.debug(f"提取的JSON文本（前200字符）: {json_text[:200]}")
            
            # 解析JSON
            try:
                problem_data = json.loads(json_text)
                logger.info("JSON解析成功")
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                logger.debug(f"原始响应: {response[:500]}")
                logger.debug(f"提取的JSON: {json_text[:500]}")
                raise
            
            # 标准化数据
            self._normalize_problem_data(problem_data, raw_text)
            
            # 保存到缓存
            self._save_to_cache(cache_key, problem_data)
            
            logger.info("题面格式化成功")
            return problem_data
            
        except Exception as e:
            logger.error(f"LLM格式化失败: {e}")
            # 回退到基础模板
            logger.info("使用基础模板")
            return self._create_fallback_problem_data(raw_text)
    
    def _compute_cache_key(self, text: str) -> str:
        """计算缓存key（MD5）"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """从缓存加载"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"读取缓存失败: {e}")
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]):
        """保存到缓存"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"保存缓存失败: {e}")
    
    def _extract_json(self, text: str) -> str:
        """从响应文本中提取JSON（支持多种格式）"""
        text = text.strip()
        
        # 1. 如果直接是JSON（以{开头）
        if text.startswith('{'):
            # 找到匹配的结束}
            brace_count = 0
            for i, char in enumerate(text):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return text[:i+1]
            # 如果没找到匹配的}，返回整个文本
            return text
        
        # 2. 尝试提取markdown代码块中的JSON
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
        
        # 3. 提取第一个完整的花括号内容
        brace_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', text, re.DOTALL)
        if brace_match:
            return brace_match.group(1).strip()
        
        # 4. 尝试更宽松的花括号匹配（可能跨越多层）
        start_idx = text.find('{')
        if start_idx != -1:
            brace_count = 0
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return text[start_idx:i+1]
        
        # 5. 直接返回原文（可能导致解析失败，但会触发fallback）
        return text
    
    def _normalize_problem_data(self, data: Dict[str, Any], raw_text: str):
        """标准化题目数据"""
        # 确保必需字段存在
        if "title" not in data:
            data["title"] = "未命名题目"
        
        if "description" not in data:
            data["description"] = raw_text[:500] + "..." if len(raw_text) > 500 else raw_text
        
        if "input_format" not in data:
            data["input_format"] = "见题目描述"
        
        if "output_format" not in data:
            data["output_format"] = "见题目描述"
        
        if "samples" not in data:
            data["samples"] = []
        
        if "hints" not in data:
            data["hints"] = ""
        
        # 设置默认值
        data.setdefault("time_limit", None)
        data.setdefault("memory_limit", None)
        data.setdefault("tags", [])
        data.setdefault("difficulty", None)
        data.setdefault("extra", {})
        
        # 清理 tags 字段
        if not isinstance(data["tags"], list):
            data["tags"] = []
        # 去除空字符串和只含空白字符的标签
        data["tags"] = [tag.strip() for tag in data["tags"] if tag and isinstance(tag, str) and tag.strip()]
    
    def _create_fallback_problem_data(self, raw_text: str) -> Dict[str, Any]:
        """创建回退模板"""
        return {
            "title": "未命名题目",
            "description": raw_text,
            "input_format": "见题目描述",
            "output_format": "见题目描述",
            "samples": [],
            "hints": "",
            "time_limit": None,
            "memory_limit": None,
            "tags": [],
            "difficulty": None,
            "extra": {}
        }
    
    def generate_problem_id(self, title: str) -> str:
        """从标题生成问题ID
        
        Args:
            title: 题目标题
            
        Returns:
            格式化的问题ID（如 manual_矩阵乘法_20250101120000）
        """
        # 1. 提取关键词（中英文、数字、下划线）
        keywords = re.sub(r'[^\w\u4e00-\u9fa5]', '', title)
        
        # 2. 转换为安全文件名
        safe_title = sanitize_filename(keywords)
        
        # 3. 截取前30字符
        safe_title = safe_title[:30]
        
        # 4. 如果为空，使用默认值
        if not safe_title:
            safe_title = "problem"
        
        # 5. 添加timestamp避免冲突
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        return f"manual_{safe_title}_{timestamp}"

