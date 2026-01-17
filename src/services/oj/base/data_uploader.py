# -*- coding: utf-8 -*-
"""数据上传接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path


class DataUploader(ABC):
    """数据上传接口"""
    
    @abstractmethod
    def upload_testcase(self, problem_id: str, data_path: Path, auth: Any) -> Dict[str, Any]:
        """上传测试数据
        
        Args:
            problem_id: 题目ID
            data_path: 数据文件路径（zip或目录）
            auth: 认证信息
            
        Returns:
            上传结果
        """
        pass
    
    @abstractmethod
    def supports_format(self, format_type: str) -> bool:
        """是否支持该数据格式
        
        Args:
            format_type: 格式类型（zip/dir/individual等）
            
        Returns:
            是否支持
        """
        pass

