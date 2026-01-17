"""
OJO 核心模块
提供事件系统、数据库等核心功能

注意：配置功能已迁移到 services.unified_config
"""

__version__ = "9.0.0"

from .events import EventBus, Event

__all__ = [
    "EventBus",
    "Event",
]

# 保留 ConfigCenter 导入以兼容旧代码（发出警告）
def __getattr__(name):
    if name == "ConfigCenter":
        import warnings
        warnings.warn(
            "core.ConfigCenter 已弃用，请使用 services.unified_config.get_config()",
            DeprecationWarning,
            stacklevel=2
        )
        from .config import ConfigCenter
        return ConfigCenter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
