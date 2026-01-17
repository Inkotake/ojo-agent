# -*- coding: utf-8 -*-
"""OJ适配器基类（重构版v7.0）"""

from abc import ABC, abstractmethod
from typing import Set, Optional, Dict, Any, List
from pathlib import Path
from loguru import logger
from .capabilities import OJCapability


class OJAdapter(ABC):
    """OJ适配器基类（v7.0重构版）
    
    实现完整的生命周期管理和健康检查功能
    所有OJ适配器都应继承此类并实现相应方法
    """
    
    def __init__(self):
        """初始化适配器"""
        self._initialized = False
        self._context: Dict[str, Any] = {}
        self._metrics = {
            "requests_total": 0,
            "requests_failed": 0,
            "uptime_seconds": 0,
        }
    
    # === 核心属性（必须实现） ===
    
    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称（唯一标识）
        
        Returns:
            适配器名称，如 'shsoj', 'codeforces'
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """显示名称（用于GUI）
        
        Returns:
            用户友好的显示名称
        """
        pass
    
    @property
    def version(self) -> str:
        """适配器版本号
        
        Returns:
            版本号字符串，如 '7.0.0'
        """
        return "7.0.0"
    
    @property
    @abstractmethod
    def capabilities(self) -> Set[OJCapability]:
        """返回支持的能力集合
        
        Returns:
            能力集合
        """
        pass
    
    # === 生命周期管理（新增） ===
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        """初始化适配器
        
        Args:
            context: 初始化上下文（包含配置、event_bus等）
        
        Returns:
            是否初始化成功
        """
        if self._initialized:
            logger.warning(f"适配器已初始化: {self.name}")
            return True
        
        try:
            self._context = context
            
            # 子类可以重写 _do_initialize 方法进行特定初始化
            if hasattr(self, '_do_initialize'):
                result = self._do_initialize(context)
                if not result:
                    return False
            
            self._initialized = True
            logger.info(f"适配器初始化成功: {self.name} v{self.version}")
            return True
        except Exception as e:
            logger.error(f"适配器初始化失败: {self.name}, 错误: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查
        
        Returns:
            健康状态信息
        """
        return {
            "healthy": self._initialized,
            "status": "ready" if self._initialized else "uninitialized",
            "message": f"{self.display_name}运行正常" if self._initialized else "未初始化",
            "metrics": self._metrics.copy(),
            "version": self.version
        }
    
    def shutdown(self) -> None:
        """关闭适配器，清理资源"""
        try:
            # 子类可以重写 _do_shutdown 方法进行特定清理
            if hasattr(self, '_do_shutdown'):
                self._do_shutdown()
            
            self._initialized = False
            logger.info(f"适配器已关闭: {self.name}")
        except Exception as e:
            logger.error(f"适配器关闭失败: {self.name}, 错误: {e}")
    
    def can_handle_url(self, url: str) -> bool:
        """检查是否能处理指定URL
        
        Args:
            url: 题目URL或ID
        
        Returns:
            是否支持
        """
        # 默认尝试使用problem_fetcher判断
        try:
            fetcher = self.get_problem_fetcher()
            if fetcher and hasattr(fetcher, 'supports_url'):
                return fetcher.supports_url(url)
        except:
            pass
        return False
    
    def get_priority(self) -> int:
        """获取优先级（用于适配器选择）
        
        Returns:
            优先级（0-100），默认50
        """
        return 50
    
    def get_problem_fetcher(self) -> Optional['ProblemFetcher']:
        """获取题面获取器
        
        Returns:
            题面获取器实例，不支持则返回None
        """
        return None
    
    def get_data_uploader(self) -> Optional['DataUploader']:
        """获取数据上传器
        
        Returns:
            数据上传器实例，不支持则返回None
        """
        return None
    
    def resolve_or_create_problem_id(self, auth: Any, original_id: str, zip_path: str = None, workspace_dir: Path = None) -> tuple[int | None, str | None, Dict[str, Any] | None]:
        """解析或创建题目ID（适配器自己判断）
        
        适配器应该自己判断：
        - 如果original_id是自己的格式，直接解析返回(actual_id, problem_id_str, None)
        - 如果不是自己的格式，尝试从本地problem_data.json创建新题目，返回(actual_id, problem_id_str, upload_result)
        
        Args:
            auth: 认证对象
            original_id: 原始题目ID或URL
            zip_path: 测试数据zip路径（可选，用于创建新题目）
            workspace_dir: 工作区目录（可选，用于读取problem_data.json）
            
        Returns:
            (actual_id, problem_id_str, upload_result)
            - actual_id: 后端ID（int），如果无法解析或创建则为None
            - problem_id_str: 显示ID（str），如果无法解析或创建则为None
            - upload_result: 上传结果字典（如果创建了新题目），否则为None
        """
        # 默认实现：返回None，表示不支持
        return None, None, None
    
    def upload_and_update_problem(self, auth: Any, original_id: str, zip_path: str, 
                                   log_callback=None, skip_update: bool = False) -> Dict[str, Any]:
        """上传测试数据并更新题目配置（适配器完整实现）
        
        这是一个统一的接口，适配器应该完整实现整个上传和更新流程：
        1. 解析或创建题目ID
        2. 上传zip文件（如果还没上传）
        3. 获取测试用例列表
        4. 获取当前题目配置
        5. 构建更新payload
        6. 更新题目配置
        
        Args:
            auth: 认证对象
            original_id: 原始题目ID或URL
            zip_path: 测试数据zip路径
            log_callback: 日志回调函数（可选）
            
        Returns:
            更新结果字典
        """
        # 默认实现：不支持
        raise NotImplementedError(f"{self.display_name}适配器不支持完整上传更新流程")
    
    def fetch_problem_cases(self, auth: Any, actual_id: int) -> List[Dict[str, Any]]:
        """获取题目的测试用例列表
        
        Args:
            auth: 认证对象
            actual_id: 后端题目ID
            
        Returns:
            测试用例列表
        """
        # 默认实现：返回空列表
        return []
    
    def fetch_admin_problem(self, auth: Any, actual_id: int) -> Dict[str, Any]:
        """获取管理员视角的题目信息
        
        Args:
            auth: 认证对象
            actual_id: 后端题目ID
            
        Returns:
            题目信息字典
        """
        # 默认实现：返回空字典
        return {}
    
    def update_problem_config(self, auth: Any, actual_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新题目配置
        
        Args:
            auth: 认证对象
            actual_id: 后端题目ID
            payload: 更新payload
            
        Returns:
            更新结果
        """
        # 默认实现：不支持
        raise NotImplementedError(f"{self.display_name}适配器不支持更新题目配置")
    
    def get_solution_submitter(self) -> Optional['SolutionSubmitter']:
        """获取解题提交器
        
        Returns:
            解题提交器实例，不支持则返回None
        """
        return None
    
    def get_training_manager(self) -> Optional['TrainingManager']:
        """获取题单管理器
        
        Returns:
            题单管理器实例，不支持则返回None
        """
        return None
    
    def get_solution_provider(self) -> Optional['SolutionProvider']:
        """获取官方题解提供器
        
        Returns:
            官方题解提供器实例，不支持则返回None
        """
        return None
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置schema（用于GUI生成配置表单）
        
        Returns:
            配置schema字典
        """
        return {}
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置是否有效
        
        Args:
            config: 配置字典
            
        Returns:
            (是否有效, 错误信息)
        """
        return True, ""

