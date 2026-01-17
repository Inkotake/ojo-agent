"""
事件系统类型定义
"""

from typing import Dict, Any, Callable, Awaitable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """事件类型枚举"""
    # 任务事件
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    
    # 适配器事件
    ADAPTER_INITIALIZED = "adapter.initialized"
    ADAPTER_READY = "adapter.ready"
    ADAPTER_DEGRADED = "adapter.degraded"
    ADAPTER_UNHEALTHY = "adapter.unhealthy"
    ADAPTER_SHUTDOWN = "adapter.shutdown"
    
    # 系统事件
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"


@dataclass
class Event:
    """事件基类"""
    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
        }


# 事件处理器类型
EventHandler = Union[
    Callable[[Event], None],
    Callable[[Event], Awaitable[None]]
]

