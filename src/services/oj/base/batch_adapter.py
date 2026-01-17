# -*- coding: utf-8 -*-
"""批量适配器基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import QWidget


class BatchAdapter(ABC):
    """批量适配器基类
    
    用于批量获取题目并添加到任务清单
    每个批量适配器可以定义自己的输入方式和获取逻辑
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称（唯一标识）
        
        Returns:
            适配器名称，如 "shsoj_batch_tag"
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """显示名称
        
        Returns:
            用户友好的显示名称，如 "SHSOJ - 按标签批量获取"
        """
        pass
    
    @abstractmethod
    def create_input_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        """创建输入界面（GUI组件）
        
        Args:
            parent: 父组件
            
        Returns:
            包含输入控件的QWidget
        """
        pass
    
    @abstractmethod
    def fetch_problem_urls(self, input_data: Dict[str, Any]) -> List[str]:
        """根据输入数据批量获取题目URL
        
        Args:
            input_data: 从输入界面提取的数据字典
            
        Returns:
            题目URL列表
        """
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> tuple[bool, str]:
        """验证输入数据
        
        Args:
            input_data: 从输入界面提取的数据字典
            
        Returns:
            (是否有效, 错误信息) 元组
            如果有效则 (True, "")
            如果无效则 (False, "错误描述")
        """
        pass

