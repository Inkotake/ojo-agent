# -*- coding: utf-8 -*-
"""批量适配器注册表"""

from typing import Dict, List, Optional
from .base.batch_adapter import BatchAdapter


class BatchAdapterRegistry:
    """批量适配器注册表
    
    管理所有批量适配器的注册与查找
    """
    
    def __init__(self):
        self._adapters: Dict[str, BatchAdapter] = {}
    
    def register(self, adapter: BatchAdapter):
        """注册批量适配器
        
        Args:
            adapter: 批量适配器实例
        """
        self._adapters[adapter.name] = adapter
    
    def get(self, name: str) -> Optional[BatchAdapter]:
        """获取指定的批量适配器
        
        Args:
            name: 适配器名称
            
        Returns:
            批量适配器实例，如果不存在则返回None
        """
        return self._adapters.get(name)
    
    def list_all(self) -> List[BatchAdapter]:
        """列出所有已注册的批量适配器
        
        Returns:
            批量适配器列表
        """
        return list(self._adapters.values())
    
    def has(self, name: str) -> bool:
        """检查指定适配器是否已注册
        
        Args:
            name: 适配器名称
            
        Returns:
            是否已注册
        """
        return name in self._adapters

