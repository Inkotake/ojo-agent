"""
预定义事件类型
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from .types import Event, EventType


@dataclass
class TaskEvent(Event):
    """任务事件"""
    task_id: str = ""
    problem_id: str = ""
    stage: str = ""
    progress: int = 0
    message: str = ""
    error: Optional[Exception] = None
    
    def __post_init__(self):
        # 自动填充data字段
        if not self.data:
            self.data = {
                "task_id": self.task_id,
                "problem_id": self.problem_id,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
            }
            if self.error:
                self.data["error"] = str(self.error)


@dataclass
class AdapterEvent(Event):
    """适配器事件"""
    adapter_name: str = ""
    status: str = ""
    message: str = ""
    health_info: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if not self.data:
            self.data = {
                "adapter_name": self.adapter_name,
                "status": self.status,
                "message": self.message,
            }
            if self.health_info:
                self.data["health_info"] = self.health_info


@dataclass
class SystemEvent(Event):
    """系统事件"""
    level: str = "INFO"
    message: str = ""
    details: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if not self.data:
            self.data = {
                "level": self.level,
                "message": self.message,
            }
            if self.details:
                self.data["details"] = self.details

