"""
配置中心类型定义
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class ConfigScope(str, Enum):
    """配置作用域"""
    SYSTEM = "system"          # 系统级配置
    ADAPTER = "adapter"        # 适配器配置
    LLM = "llm"               # LLM配置
    PIPELINE = "pipeline"      # Pipeline配置
    USER = "user"             # 用户配置


@dataclass
class ConfigEntry:
    """配置条目"""
    key: str
    value: Any
    scope: ConfigScope
    description: str = ""
    required: bool = False
    default: Any = None
    
    def validate(self) -> bool:
        """验证配置值"""
        if self.required and self.value is None:
            return False
        return True

