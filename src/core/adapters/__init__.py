"""
适配器抽象层 - 新接口定义
提供适配器生命周期管理、健康检查等功能
"""

from .interface import IAdapter, AdapterContext
from .lifecycle import AdapterLifecycle, LifecycleState
from .manager import AdapterLifecycleManager
from .capabilities import AdapterCapability

__all__ = [
    "IAdapter",
    "AdapterContext",
    "AdapterLifecycle",
    "LifecycleState",
    "AdapterLifecycleManager",
    "AdapterCapability",
]

