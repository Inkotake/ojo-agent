# -*- coding: utf-8 -*-
"""题面获取接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ProblemFetcher(ABC):
    """题面获取接口"""
    
    @abstractmethod
    def supports_url(self, url: str) -> bool:
        """判断是否支持该URL
        
        Args:
            url: 题目URL
            
        Returns:
            是否支持该URL
        """
        pass
    
    @abstractmethod
    def parse_problem_id(self, input_str: str) -> Optional[str]:
        """从URL或ID字符串中解析题目ID
        
        Args:
            input_str: URL或ID字符串
            
        Returns:
            解析出的题目ID，失败返回None
        """
        pass
    
    @abstractmethod
    def fetch_problem(self, problem_id: str) -> Dict[str, Any]:
        """获取题目信息，返回标准格式
        
        Args:
            problem_id: 题目ID
            
        Returns:
            题目信息字典（标准格式）
        """
        pass

