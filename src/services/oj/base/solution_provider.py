# -*- coding: utf-8 -*-
"""官方题解提供接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class SolutionProvider(ABC):
    """官方题解提供接口（Editorial）"""
    
    @abstractmethod
    def has_official_solution(self, problem_id: str) -> bool:
        """判断该题目是否有官方题解
        
        Args:
            problem_id: 题目ID
            
        Returns:
            是否有官方题解
        """
        pass
    
    @abstractmethod
    def fetch_solution(self, problem_id: str) -> Optional[Dict[str, Any]]:
        """获取官方题解
        
        Args:
            problem_id: 题目ID
            
        Returns:
            题解数据，格式：
            {
                "problem_id": str,
                "source": str,  # 题解来源（official/community）
                "title": str,   # 题解标题
                "content": str, # 题解内容（Markdown或纯文本）
                "author": str,  # 作者
                "language": str, # 语言（zh/en）
                "url": str,     # 原始URL
                "code_samples": [  # 代码示例（可选）
                    {
                        "language": str,
                        "code": str,
                        "description": str
                    }
                ],
                "algorithm": str,  # 算法标签（可选）
                "complexity": {    # 复杂度（可选）
                    "time": str,
                    "space": str
                }
            }
        """
        pass

