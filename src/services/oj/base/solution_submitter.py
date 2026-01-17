# -*- coding: utf-8 -*-
"""解题提交接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class SolutionSubmitter(ABC):
    """解题提交接口"""
    
    @abstractmethod
    def submit_solution(self, problem_id: str, code: str, language: str, auth: Any) -> Dict[str, Any]:
        """提交解题代码
        
        Args:
            problem_id: 题目ID
            code: 代码内容
            language: 编程语言
            auth: 认证信息
            
        Returns:
            提交结果（包含提交ID等）
        """
        pass
    
    @abstractmethod
    def get_submission_status(self, submission_id: str, auth: Any) -> Dict[str, Any]:
        """查询提交状态
        
        Args:
            submission_id: 提交ID
            auth: 认证信息
            
        Returns:
            提交状态信息
        """
        pass
    
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """获取支持的编程语言列表
        
        Returns:
            语言列表
        """
        pass
    
    def get_default_language(self, lang_hint: str = "C++") -> str:
        """获取默认语言键（子类可覆盖）
        
        Args:
            lang_hint: 语言提示（如 "C++", "Python"）
            
        Returns:
            适配器使用的语言键
        """
        # 默认实现：返回提示本身
        return lang_hint

