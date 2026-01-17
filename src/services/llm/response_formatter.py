# -*- coding: utf-8 -*-
"""LLM响应格式化 - 统一处理代码提取和清洗"""

from __future__ import annotations
from utils.text import sanitize_code, sanitize_cpp_code


class ResponseFormatter:
    """LLM响应格式化（代码清洗、提取）
    
    职责：
    - 从LLM响应中提取代码
    - 清洗代码（移除markdown、注释等）
    - 统一错误处理
    """
    
    @staticmethod
    def extract_python_code(response: str, pid: str) -> str:
        """提取并清洗Python代码
        
        Args:
            response: LLM原始响应
            pid: 题目ID（用于清洗）
            
        Returns:
            清洗后的Python代码
            
        Raises:
            ValueError: 如果无法提取有效代码
        """
        if not response or not response.strip():
            raise ValueError("LLM响应为空")
        
        # 使用统一的清洗逻辑
        cleaned_code = sanitize_code(response, pid)
        
        if not cleaned_code or len(cleaned_code) < 10:
            raise ValueError(f"清洗后代码过短（{len(cleaned_code)}字符）")
        
        return cleaned_code
    
    @staticmethod
    def extract_cpp_code(response: str) -> str:
        """提取并清洗C++代码
        
        Args:
            response: LLM原始响应
            
        Returns:
            清洗后的C++代码
            
        Raises:
            ValueError: 如果无法提取有效代码
        """
        if not response or not response.strip():
            raise ValueError("LLM响应为空")
        
        # 使用统一的清洗逻辑
        cleaned_code = sanitize_cpp_code(response)
        
        if not cleaned_code or len(cleaned_code) < 10:
            raise ValueError(f"清洗后代码过短（{len(cleaned_code)}字符）")
        
        # C++特定验证
        if '#include' not in cleaned_code:
            raise ValueError("C++代码缺少#include语句")
        
        return cleaned_code
    
    @staticmethod
    def validate_python_generator(code: str) -> bool:
        """验证Python生成器代码的基本结构
        
        Args:
            code: Python代码
            
        Returns:
            是否包含必需元素
        """
        required_elements = [
            'import ',
            'def ',
            'PROBLEM_ID',
            '.zip'
        ]
        
        return all(elem in code for elem in required_elements)
    
    @staticmethod
    def validate_cpp_solution(code: str) -> bool:
        """验证C++解题代码的基本结构
        
        Args:
            code: C++代码
            
        Returns:
            是否包含必需元素
        """
        required_elements = [
            '#include',
            'int main'
        ]
        
        return all(elem in code for elem in required_elements)

