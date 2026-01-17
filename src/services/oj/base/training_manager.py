# -*- coding: utf-8 -*-
"""题单管理接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class TrainingManager(ABC):
    """题单管理接口"""
    
    @abstractmethod
    def create_training(self, title: str, description: str, auth: Any, **kwargs) -> Dict[str, Any]:
        """创建题单
        
        Args:
            title: 题单标题
            description: 题单描述
            auth: 认证信息
            **kwargs: 其他平台特定参数
            
        Returns:
            创建结果（包含题单ID）
        """
        pass
    
    @abstractmethod
    def add_problems(self, training_id: str, problem_ids: List[str], auth: Any) -> Dict[str, Any]:
        """添加题目到题单
        
        Args:
            training_id: 题单ID
            problem_ids: 题目ID列表
            auth: 认证信息
            
        Returns:
            添加结果
        """
        pass
    
    @abstractmethod
    def get_training(self, training_id: str, auth: Any) -> Dict[str, Any]:
        """获取题单信息
        
        Args:
            training_id: 题单ID
            auth: 认证信息
            
        Returns:
            题单信息
        """
        pass

