"""
模板系统类型定义
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class TemplateType(str, Enum):
    """模板类型"""
    DATA_GENERATION = "data_generation"
    SOLUTION = "solution"
    OCR = "ocr"
    SUMMARY = "summary"
    ERROR_FIX = "error_fix"


@dataclass
class Template:
    """模板定义"""
    name: str
    type: TemplateType
    content: str
    variables: List[str] = field(default_factory=list)
    description: str = ""
    
    def validate(self, context: Dict[str, Any]) -> bool:
        """验证上下文是否包含所有必需变量"""
        return all(var in context for var in self.variables)


@dataclass
class TemplateContext:
    """模板渲染上下文"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def set(self, key: str, value: Any) -> None:
        """设置变量"""
        self.data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取变量"""
        return self.data.get(key, default)
    
    def update(self, data: Dict[str, Any]) -> None:
        """批量更新"""
        self.data.update(data)

