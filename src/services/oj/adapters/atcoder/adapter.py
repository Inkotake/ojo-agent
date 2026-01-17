# -*- coding: utf-8 -*-
"""AtCoder适配器"""
from typing import Set, Dict, Any
from ...base import OJAdapter, OJCapability, ProblemFetcher

class AtCoderAdapter(OJAdapter):
    """AtCoder适配器（v7.0重构版）"""
    def __init__(self):
        super().__init__()
    
    @property
    def name(self) -> str:
        return "atcoder"
    
    @property
    def display_name(self) -> str:
        return "AtCoder"
    
    @property
    def capabilities(self) -> Set[OJCapability]:
        return {OJCapability.FETCH_PROBLEM}
    
    def get_problem_fetcher(self) -> ProblemFetcher:
        from .problem_fetcher_impl import AtCoderProblemFetcher
        return AtCoderProblemFetcher()
    
    def get_config_schema(self) -> Dict[str, Any]:
        """AtCoder 公开API，无需配置"""
        return {}
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """无需验证"""
        return True, ""

