# -*- coding: utf-8 -*-
"""洛谷适配器"""
from typing import Set, Optional, Dict, Any
from ...base import OJAdapter, OJCapability, ProblemFetcher, SolutionProvider

class LuoguAdapter(OJAdapter):
    """洛谷适配器（v7.0重构版）"""
    def __init__(self):
        super().__init__()
        self._problem_fetcher = None
        self._solution_provider = None
    
    @property
    def name(self) -> str:
        return "luogu"
    
    @property
    def display_name(self) -> str:
        return "洛谷"
    
    @property
    def capabilities(self) -> Set[OJCapability]:
        return {
            OJCapability.FETCH_PROBLEM,
            OJCapability.PROVIDE_SOLUTION  # 支持官方题解
        }
    
    def get_problem_fetcher(self) -> ProblemFetcher:
        if not self._problem_fetcher:
            from .problem_fetcher_impl import LuoguProblemFetcher
            self._problem_fetcher = LuoguProblemFetcher()
        return self._problem_fetcher
    
    def get_solution_provider(self) -> Optional[SolutionProvider]:
        if not self._solution_provider:
            from .solution_provider_impl import LuoguSolutionProvider
            self._solution_provider = LuoguSolutionProvider()
        return self._solution_provider
    
    def get_config_schema(self) -> Dict[str, Any]:
        """洛谷公开API，无需配置"""
        return {}
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """无需验证"""
        return True, ""

