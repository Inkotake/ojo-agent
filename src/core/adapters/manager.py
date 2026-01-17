"""
适配器生命周期管理器
"""

from typing import Dict, List, Optional
from loguru import logger

from .interface import IAdapter, AdapterContext
from .lifecycle import LifecycleState


class AdapterLifecycleManager:
    """
    适配器生命周期管理器
    负责管理所有适配器的生命周期
    """
    
    def __init__(self):
        self._adapters: Dict[str, IAdapter] = {}
        self._states: Dict[str, LifecycleState] = {}
        self._health_info: Dict[str, Dict] = {}
    
    def register(self, adapter: IAdapter) -> None:
        """
        注册适配器
        
        Args:
            adapter: 适配器实例
        """
        name = adapter.name
        if name in self._adapters:
            logger.warning(f"适配器已存在，将被覆盖: {name}")
        
        self._adapters[name] = adapter
        self._states[name] = LifecycleState.UNINITIALIZED
        
        logger.info(f"注册适配器: {name} ({adapter.display_name})")
    
    def initialize(self, adapter_name: str, context: AdapterContext) -> bool:
        """
        初始化适配器
        
        Args:
            adapter_name: 适配器名称
            context: 适配器上下文
        
        Returns:
            是否初始化成功
        """
        adapter = self._adapters.get(adapter_name)
        if not adapter:
            logger.error(f"适配器不存在: {adapter_name}")
            return False
        
        # 检查当前状态
        current_state = self._states.get(adapter_name)
        if current_state != LifecycleState.UNINITIALIZED:
            logger.warning(f"适配器已初始化: {adapter_name}, 状态: {current_state}")
            return current_state.is_operational()
        
        # 开始初始化
        self._states[adapter_name] = LifecycleState.INITIALIZING
        logger.info(f"初始化适配器: {adapter_name}")
        
        try:
            success = adapter.initialize(context)
            
            if success:
                self._states[adapter_name] = LifecycleState.READY
                logger.info(f"适配器初始化成功: {adapter_name}")
            else:
                self._states[adapter_name] = LifecycleState.UNHEALTHY
                logger.error(f"适配器初始化失败: {adapter_name}")
            
            return success
        except Exception as e:
            self._states[adapter_name] = LifecycleState.UNHEALTHY
            logger.error(f"适配器初始化异常: {adapter_name}, 错误: {e}")
            return False
    
    def check_health(self, adapter_name: str) -> Dict:
        """
        检查适配器健康状态
        
        Args:
            adapter_name: 适配器名称
        
        Returns:
            健康状态信息
        """
        adapter = self._adapters.get(adapter_name)
        if not adapter:
            return {
                "healthy": False,
                "status": "not_found",
                "message": f"适配器不存在: {adapter_name}"
            }
        
        try:
            health_info = adapter.health_check()
            self._health_info[adapter_name] = health_info
            
            # 更新状态
            if health_info.get("healthy"):
                if health_info.get("status") == "degraded":
                    self._states[adapter_name] = LifecycleState.DEGRADED
                else:
                    self._states[adapter_name] = LifecycleState.READY
            else:
                self._states[adapter_name] = LifecycleState.UNHEALTHY
            
            return health_info
        except Exception as e:
            logger.error(f"健康检查失败: {adapter_name}, 错误: {e}")
            self._states[adapter_name] = LifecycleState.UNHEALTHY
            return {
                "healthy": False,
                "status": "error",
                "message": str(e)
            }
    
    def shutdown(self, adapter_name: str) -> None:
        """
        关闭适配器
        
        Args:
            adapter_name: 适配器名称
        """
        adapter = self._adapters.get(adapter_name)
        if not adapter:
            logger.warning(f"适配器不存在: {adapter_name}")
            return
        
        self._states[adapter_name] = LifecycleState.SHUTTING_DOWN
        logger.info(f"关闭适配器: {adapter_name}")
        
        try:
            adapter.shutdown()
            self._states[adapter_name] = LifecycleState.SHUTDOWN
            logger.info(f"适配器已关闭: {adapter_name}")
        except Exception as e:
            logger.error(f"适配器关闭失败: {adapter_name}, 错误: {e}")
    
    def shutdown_all(self) -> None:
        """关闭所有适配器"""
        logger.info("关闭所有适配器...")
        for adapter_name in list(self._adapters.keys()):
            self.shutdown(adapter_name)
    
    def get_adapter(self, adapter_name: str) -> Optional[IAdapter]:
        """获取适配器实例"""
        return self._adapters.get(adapter_name)
    
    def get_state(self, adapter_name: str) -> LifecycleState:
        """获取适配器状态"""
        return self._states.get(adapter_name, LifecycleState.UNINITIALIZED)
    
    def list_adapters(self) -> List[Dict]:
        """
        列出所有适配器
        
        Returns:
            适配器信息列表
        """
        result = []
        for name, adapter in self._adapters.items():
            result.append({
                "name": name,
                "display_name": adapter.display_name,
                "version": adapter.version,
                "state": self._states.get(name, LifecycleState.UNINITIALIZED).value,
                "capabilities": [str(cap) for cap in adapter.capabilities],
                "health": self._health_info.get(name, {})
            })
        return result
    
    def is_ready(self, adapter_name: str) -> bool:
        """检查适配器是否就绪"""
        state = self._states.get(adapter_name)
        return state and state.is_operational()


# 全局适配器生命周期管理器实例
_global_adapter_manager: AdapterLifecycleManager = None


def get_adapter_manager() -> AdapterLifecycleManager:
    """获取全局适配器生命周期管理器实例"""
    global _global_adapter_manager
    if _global_adapter_manager is None:
        _global_adapter_manager = AdapterLifecycleManager()
    return _global_adapter_manager

