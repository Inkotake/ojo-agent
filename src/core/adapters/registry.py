"""
增强版适配器注册表
集成生命周期管理、事件发布等功能
"""

from typing import Optional, List, Dict, Any
from loguru import logger

from .interface import IAdapter, AdapterContext
from .wrapper import AdapterWrapper
from .manager import AdapterLifecycleManager
from .capabilities import AdapterCapability
from services.oj.base.adapter_base import OJAdapter


class EnhancedAdapterRegistry:
    """
    增强版适配器注册表
    支持新旧适配器接口，提供生命周期管理
    """
    
    def __init__(self, lifecycle_manager: AdapterLifecycleManager = None):
        """
        Args:
            lifecycle_manager: 生命周期管理器（可选）
        """
        self._manager = lifecycle_manager or AdapterLifecycleManager()
        self._url_patterns: Dict[str, str] = {}  # URL模式 -> 适配器名称
    
    def register(self, adapter: IAdapter) -> None:
        """
        注册适配器（新接口）
        
        Args:
            adapter: 实现IAdapter接口的适配器
        """
        self._manager.register(adapter)
        logger.info(f"注册新接口适配器: {adapter.name}")
    
    def register_legacy(self, adapter: OJAdapter) -> None:
        """
        注册旧版适配器（自动包装为新接口）
        
        Args:
            adapter: 旧版OJAdapter
        """
        # 包装为新接口
        wrapped = AdapterWrapper(adapter)
        self._manager.register(wrapped)
        logger.info(f"注册旧版适配器（已包装）: {adapter.name}")
    
    def auto_register_from_legacy_registry(self) -> None:
        """
        从旧注册表自动导入所有适配器
        保持兼容性
        """
        try:
            from services.oj.registry import registry as legacy_registry
            
            # 获取所有旧版适配器
            all_adapters = legacy_registry._adapters.values()
            
            for adapter in all_adapters:
                self.register_legacy(adapter)
            
            logger.info(f"从旧注册表导入 {len(all_adapters)} 个适配器")
        except Exception as e:
            logger.error(f"自动导入适配器失败: {e}")
    
    def get_adapter(self, adapter_name: str, 
                    context: AdapterContext = None) -> Optional[IAdapter]:
        """
        获取适配器（自动初始化）
        
        Args:
            adapter_name: 适配器名称
            context: 适配器上下文（首次获取时需要）
        
        Returns:
            适配器实例（已初始化）或None
        """
        adapter = self._manager.get_adapter(adapter_name)
        if not adapter:
            logger.warning(f"适配器不存在: {adapter_name}")
            return None
        
        # 检查是否已初始化
        if not self._manager.is_ready(adapter_name):
            if context:
                # 尝试初始化
                success = self._manager.initialize(adapter_name, context)
                if not success:
                    logger.error(f"适配器初始化失败: {adapter_name}")
                    return None
            else:
                logger.warning(f"适配器未初始化且未提供上下文: {adapter_name}")
                return None
        
        return adapter
    
    def find_adapter_by_url(self, url: str, 
                           context: AdapterContext = None) -> Optional[IAdapter]:
        """
        根据URL查找适配器
        
        Args:
            url: 题目URL或ID
            context: 适配器上下文
        
        Returns:
            匹配的适配器或None
        """
        # 遍历所有适配器，按优先级排序
        candidates = []
        
        for adapter_info in self._manager.list_adapters():
            adapter_name = adapter_info['name']
            adapter = self._manager.get_adapter(adapter_name)
            
            if adapter and adapter.can_handle_url(url):
                priority = adapter.get_priority()
                candidates.append((priority, adapter_name, adapter))
        
        if not candidates:
            logger.warning(f"未找到支持该URL的适配器: {url}")
            return None
        
        # 按优先级排序（降序）
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # 返回优先级最高的适配器
        _, adapter_name, adapter = candidates[0]
        
        # 确保已初始化
        if not self._manager.is_ready(adapter_name) and context:
            self._manager.initialize(adapter_name, context)
        
        logger.info(f"URL匹配适配器: {url} -> {adapter_name}")
        return adapter
    
    def find_adapter_with_capability(self, capability: AdapterCapability,
                                     url: str = None,
                                     context: AdapterContext = None) -> Optional[IAdapter]:
        """
        查找支持特定能力的适配器
        
        Args:
            capability: 所需能力
            url: 可选的URL（用于进一步筛选）
            context: 适配器上下文
        
        Returns:
            匹配的适配器或None
        """
        candidates = []
        
        for adapter_info in self._manager.list_adapters():
            adapter_name = adapter_info['name']
            adapter = self._manager.get_adapter(adapter_name)
            
            if not adapter:
                continue
            
            # 检查能力
            if not adapter.supports_capability(capability):
                continue
            
            # 如果提供了URL，检查是否支持
            if url and not adapter.can_handle_url(url):
                continue
            
            priority = adapter.get_priority()
            candidates.append((priority, adapter_name, adapter))
        
        if not candidates:
            logger.warning(f"未找到支持该能力的适配器: {capability}")
            return None
        
        # 按优先级排序
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        _, adapter_name, adapter = candidates[0]
        
        # 确保已初始化
        if not self._manager.is_ready(adapter_name) and context:
            self._manager.initialize(adapter_name, context)
        
        return adapter
    
    def list_all_adapters(self) -> List[Dict[str, Any]]:
        """列出所有适配器"""
        return self._manager.list_adapters()
    
    def check_health(self, adapter_name: str) -> Dict[str, Any]:
        """检查适配器健康状态"""
        return self._manager.check_health(adapter_name)
    
    def check_all_health(self) -> Dict[str, Dict[str, Any]]:
        """检查所有适配器健康状态"""
        results = {}
        for adapter_info in self._manager.list_adapters():
            adapter_name = adapter_info['name']
            results[adapter_name] = self.check_health(adapter_name)
        return results
    
    def shutdown_all(self) -> None:
        """关闭所有适配器"""
        self._manager.shutdown_all()


# 全局增强版注册表实例
_enhanced_registry: EnhancedAdapterRegistry = None


def get_enhanced_registry() -> EnhancedAdapterRegistry:
    """获取全局增强版注册表实例"""
    global _enhanced_registry
    if _enhanced_registry is None:
        _enhanced_registry = EnhancedAdapterRegistry()
        # 自动从旧注册表导入
        _enhanced_registry.auto_register_from_legacy_registry()
    return _enhanced_registry

