"""
适配器接口定义
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Set, Optional
from dataclasses import dataclass, field

from .capabilities import AdapterCapability


@dataclass
class AdapterContext:
    """适配器上下文"""
    config: Dict[str, Any] = field(default_factory=dict)
    workspace_dir: str = ""
    event_bus: Any = None  # EventBus实例
    config_center: Any = None  # ConfigCenter实例
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        return self.config.get(key, default)


class IAdapter(ABC):
    """
    适配器新接口（v7.0）
    定义适配器的完整生命周期和能力
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """适配器唯一标识"""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """适配器显示名称"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """适配器版本"""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> Set[AdapterCapability]:
        """支持的能力集合"""
        pass
    
    @abstractmethod
    def initialize(self, context: AdapterContext) -> bool:
        """
        初始化适配器
        
        Args:
            context: 适配器上下文
        
        Returns:
            是否初始化成功
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态信息，格式：
            {
                "healthy": True/False,
                "status": "ready" / "degraded" / "unhealthy",
                "message": "状态描述",
                "metrics": {
                    "uptime": 1234,
                    "requests_total": 100,
                    "requests_failed": 5,
                    ...
                }
            }
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """关闭适配器，清理资源"""
        pass
    
    def can_handle_url(self, url: str) -> bool:
        """
        检查是否能处理指定URL
        
        Args:
            url: 题目URL或ID
        
        Returns:
            是否支持
        """
        return False
    
    def get_priority(self) -> int:
        """
        获取优先级（用于适配器选择）
        数值越大优先级越高
        
        Returns:
            优先级（0-100）
        """
        return 50
    
    def supports_capability(self, capability: AdapterCapability) -> bool:
        """检查是否支持某个能力"""
        return capability in self.capabilities
    
    # === 可选的内部管理方法 ===
    
    def _get_rate_limiter(self):
        """获取限流器（内部使用）"""
        return None
    
    def _get_cache_manager(self):
        """获取缓存管理器（内部使用）"""
        return None
    
    def _get_auth_manager(self):
        """获取认证管理器（内部使用）"""
        return None

