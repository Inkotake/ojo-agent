"""
适配器包装器
将现有的OJAdapter包装为新的IAdapter接口，保持底层API调用不变
"""

from typing import Set, Dict, Any
from loguru import logger

from .interface import IAdapter, AdapterContext
from .capabilities import AdapterCapability as NewCapability
from services.oj.base.adapter_base import OJAdapter
from services.oj.base.capabilities import OJCapability as OldCapability


class AdapterWrapper(IAdapter):
    """
    适配器包装器
    将旧的OJAdapter包装为新的IAdapter接口
    保持所有底层API调用完全不变
    """
    
    def __init__(self, legacy_adapter: OJAdapter):
        """
        Args:
            legacy_adapter: 旧版适配器实例
        """
        self._adapter = legacy_adapter
        self._context: AdapterContext = None
        self._initialized = False
        self._metrics = {
            "requests_total": 0,
            "requests_failed": 0,
            "uptime_seconds": 0,
        }
    
    @property
    def name(self) -> str:
        """适配器唯一标识"""
        return self._adapter.name
    
    @property
    def display_name(self) -> str:
        """适配器显示名称"""
        # 旧版可能没有display_name，使用name
        return getattr(self._adapter, 'display_name', self._adapter.name.upper())
    
    @property
    def version(self) -> str:
        """适配器版本"""
        # 旧版可能没有版本号
        return getattr(self._adapter, 'version', '6.0.0')
    
    @property
    def capabilities(self) -> Set[NewCapability]:
        """支持的能力集合（转换为新的能力枚举）"""
        old_caps = self._adapter.capabilities
        new_caps = set()
        
        # 转换能力枚举
        mapping = {
            OldCapability.FETCH_PROBLEM: NewCapability.FETCH_PROBLEM,
            OldCapability.UPLOAD_DATA: NewCapability.UPLOAD_DATA,
            OldCapability.SUBMIT_SOLUTION: NewCapability.SUBMIT_SOLUTION,
            OldCapability.MANAGE_TRAINING: NewCapability.MANAGE_TRAINING,
            OldCapability.FETCH_OFFICIAL_SOLUTION: NewCapability.FETCH_OFFICIAL_SOLUTION,
            OldCapability.BATCH_OPERATIONS: NewCapability.BATCH_OPERATIONS,
        }
        
        for old_cap in old_caps:
            if old_cap in mapping:
                new_caps.add(mapping[old_cap])
        
        # 添加默认的高级能力（如果适配器实现了相关方法）
        if hasattr(self._adapter, 'health_check'):
            new_caps.add(NewCapability.HEALTH_CHECK)
        
        return new_caps
    
    def initialize(self, context: AdapterContext) -> bool:
        """
        初始化适配器
        
        Args:
            context: 适配器上下文
        
        Returns:
            是否初始化成功
        """
        if self._initialized:
            logger.warning(f"适配器已初始化: {self.name}")
            return True
        
        self._context = context
        
        try:
            # 如果旧版适配器有初始化方法，调用它
            if hasattr(self._adapter, 'initialize'):
                result = self._adapter.initialize(context.config)
                self._initialized = result
                return result
            
            # 否则直接标记为已初始化
            self._initialized = True
            logger.info(f"适配器初始化成功（无需初始化方法）: {self.name}")
            return True
        except Exception as e:
            logger.error(f"适配器初始化失败: {self.name}, 错误: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态信息
        """
        # 基础健康状态
        health_info = {
            "healthy": self._initialized,
            "status": "ready" if self._initialized else "uninitialized",
            "message": "适配器运行正常" if self._initialized else "适配器未初始化",
            "metrics": self._metrics.copy()
        }
        
        # 如果旧版适配器有健康检查方法，调用它
        if hasattr(self._adapter, 'health_check'):
            try:
                legacy_health = self._adapter.health_check()
                if legacy_health:
                    health_info.update(legacy_health)
            except Exception as e:
                logger.warning(f"旧版健康检查失败: {self.name}, 错误: {e}")
        
        return health_info
    
    def shutdown(self) -> None:
        """关闭适配器，清理资源"""
        try:
            # 如果旧版适配器有关闭方法，调用它
            if hasattr(self._adapter, 'shutdown'):
                self._adapter.shutdown()
            
            self._initialized = False
            logger.info(f"适配器已关闭: {self.name}")
        except Exception as e:
            logger.error(f"适配器关闭失败: {self.name}, 错误: {e}")
    
    def can_handle_url(self, url: str) -> bool:
        """检查是否能处理指定URL"""
        # 调用旧版适配器的方法
        if hasattr(self._adapter, 'can_handle_url'):
            return self._adapter.can_handle_url(url)
        
        # 否则尝试使用problem_fetcher判断
        try:
            fetcher = self._adapter.get_problem_fetcher()
            if fetcher and hasattr(fetcher, 'supports_url'):
                return fetcher.supports_url(url)
        except:
            pass
        
        return False
    
    def get_priority(self) -> int:
        """获取优先级"""
        # 使用旧版适配器的优先级，如果有的话
        return getattr(self._adapter, 'priority', 50)
    
    # === 代理方法：直接调用旧版适配器 ===
    
    def get_problem_fetcher(self):
        """获取题面获取器（代理到旧版）"""
        return self._adapter.get_problem_fetcher()
    
    def get_data_uploader(self):
        """获取数据上传器（代理到旧版）"""
        return self._adapter.get_data_uploader()
    
    def get_solution_submitter(self):
        """获取代码提交器（代理到旧版）"""
        return self._adapter.get_solution_submitter()
    
    def get_training_manager(self):
        """获取题单管理器（代理到旧版）"""
        return self._adapter.get_training_manager()
    
    def get_solution_provider(self):
        """获取题解提供器（代理到旧版）"""
        return self._adapter.get_solution_provider()
    
    def get_batch_adapter(self):
        """获取批量操作器（代理到旧版）"""
        if hasattr(self._adapter, 'get_batch_adapter'):
            return self._adapter.get_batch_adapter()
        return None
    
    @property
    def legacy_adapter(self) -> OJAdapter:
        """获取旧版适配器实例（用于兼容性）"""
        return self._adapter
    
    def __getattr__(self, name: str):
        """
        代理未定义的属性/方法到旧版适配器
        保证100%兼容性
        """
        return getattr(self._adapter, name)

