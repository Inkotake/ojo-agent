"""
适配器生命周期定义
"""

from enum import Enum
from typing import Protocol, Dict, Any


class LifecycleState(str, Enum):
    """适配器生命周期状态"""
    UNINITIALIZED = "uninitialized"      # 未初始化
    INITIALIZING = "initializing"        # 初始化中
    READY = "ready"                      # 就绪
    DEGRADED = "degraded"                # 降级
    UNHEALTHY = "unhealthy"              # 不健康
    SHUTTING_DOWN = "shutting_down"      # 关闭中
    SHUTDOWN = "shutdown"                # 已关闭
    
    def is_operational(self) -> bool:
        """是否可以正常工作"""
        return self in [LifecycleState.READY, LifecycleState.DEGRADED]
    
    def is_healthy(self) -> bool:
        """是否健康"""
        return self == LifecycleState.READY


class AdapterLifecycle(Protocol):
    """
    适配器生命周期协议
    适配器可以实现此协议来提供生命周期管理
    """
    
    def on_initialize(self, context: Dict[str, Any]) -> None:
        """初始化时调用"""
        ...
    
    def on_ready(self) -> None:
        """就绪时调用"""
        ...
    
    def on_degraded(self, reason: str) -> None:
        """降级时调用"""
        ...
    
    def on_unhealthy(self, reason: str) -> None:
        """不健康时调用"""
        ...
    
    def on_shutdown(self) -> None:
        """关闭时调用"""
        ...

