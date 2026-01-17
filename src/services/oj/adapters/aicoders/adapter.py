# -*- coding: utf-8 -*-
"""Aicoders 适配器（仅拉取题目）"""

from typing import Set, Optional, Dict, Any
from pathlib import Path

from ...base.adapter_base import OJAdapter
from ...base.capabilities import OJCapability
from ...base.problem_fetcher import ProblemFetcher
from .problem_fetcher_impl import AicodersProblemFetcher


class AicodersAdapter(OJAdapter):
    """Aicoders 适配器
    
    专门用于从 https://oj.aicoders.cn 拉取题目
    不支持上传和提交（这些功能由 SHSOJ 适配器提供）
    """
    
    def __init__(self):
        super().__init__()
        self._problem_fetcher = None
        self.base_url = "https://oj.aicoders.cn"
    
    @property
    def name(self) -> str:
        return "aicoders"
    
    @property
    def display_name(self) -> str:
        return "Aicoders (oj.aicoders.cn)"
    
    @property
    def capabilities(self) -> Set[OJCapability]:
        return {OJCapability.FETCH_PROBLEM}
    
    def get_problem_fetcher(self) -> Optional[ProblemFetcher]:
        """返回题面获取器"""
        if not self._problem_fetcher:
            self._problem_fetcher = AicodersProblemFetcher(
                base_url=self.base_url,
                timeout=300,
                proxies=None,
                verify_ssl=True
            )
        return self._problem_fetcher
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置schema（Aicoders 不需要特殊配置）"""
        return {
            "base_url": {
                "type": "string", 
                "label": "前端URL", 
                "default": "https://oj.aicoders.cn", 
                "description": "Aicoders 前端 URL",
                "required": False
            }
        }
    
    def validate_config(self, config: Dict[str, str]) -> tuple[bool, Optional[str]]:
        """验证配置（总是成功）"""
        return True, None

