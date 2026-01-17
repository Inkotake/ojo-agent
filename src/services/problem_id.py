# -*- coding: utf-8 -*-
"""
题目ID统一解析模块

将分散在 generator.py, solver.py, adapter.py 中的ID规范化逻辑统一到此处。

使用方式:
    from services.problem_id import get_problem_id_resolver
    
    resolver = get_problem_id_resolver()
    canonical_id = resolver.canonicalize("https://oj.aicoders.cn/problem/2772")
    # 返回: "aicoders_2772"
    
    workspace_dir = resolver.get_workspace_dir("2772", user_id=1)
    # 返回: Path("workspace/user_1/problem_shsoj_2772")
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, TYPE_CHECKING

from loguru import logger

from utils.text import sanitize_filename

if TYPE_CHECKING:
    from services.oj.registry import AdapterRegistry
    from services.oj.base.adapter_base import OJAdapter


class ProblemIdResolver:
    """题目ID统一解析器
    
    职责:
    - 规范化各种格式的题目ID (URL/纯数字/带前缀)
    - 计算工作区目录路径
    - 解析适配器和题目ID
    """
    
    def __init__(self, registry: 'AdapterRegistry', default_adapter: str = "shsoj", 
                 default_base_url: str = "https://oj.aicoders.cn"):
        """初始化解析器
        
        Args:
            registry: 适配器注册表
            default_adapter: 纯数字ID使用的默认适配器名称
            default_base_url: 默认平台的基础URL (用于构造完整URL)
        """
        self.registry = registry
        self.default_adapter = default_adapter
        self.default_base_url = default_base_url.rstrip("/")
    
    def is_pure_numeric(self, raw_id: str) -> bool:
        """判断是否为纯数字ID
        
        Args:
            raw_id: 原始ID
            
        Returns:
            是否为1-10位纯数字
        """
        stripped = raw_id.strip()
        return stripped.isdigit() and 1 <= len(stripped) <= 10
    
    def find_adapter(self, raw_id: str) -> Tuple[Optional['OJAdapter'], str]:
        """根据ID查找适配器
        
        Args:
            raw_id: 原始ID (URL/纯数字/带前缀)
            
        Returns:
            (适配器实例, 用于解析的ID)
            如果是纯数字，会构造完整URL后查找
        """
        stripped = raw_id.strip()
        
        # 纯数字ID: 构造URL后查找
        if self.is_pure_numeric(stripped):
            constructed_url = f"{self.default_base_url}/problem/{stripped}"
            logger.debug(f"[ProblemIdResolver] 纯数字ID {stripped}，构造URL: {constructed_url}")
            adapter = self.registry.find_adapter_by_url(constructed_url)
            return adapter, constructed_url if adapter else stripped
        
        # 非纯数字: 直接尝试URL匹配
        adapter = self.registry.find_adapter_by_url(stripped)
        return adapter, stripped
    
    def canonicalize(self, raw_id: str) -> str:
        """规范化题目ID
        
        将各种格式的ID转换为统一的 "适配器名_题目ID" 格式。
        
        Args:
            raw_id: 原始ID，支持以下格式:
                - 完整URL: https://oj.aicoders.cn/problem/2772
                - 纯数字ID: 2772 (使用默认平台)
                - 带前缀ID: shsoj_2772 (直接返回)
            
        Returns:
            规范化ID，如 "aicoders_2772"
            如果无法解析则返回原始ID
        """
        try:
            adapter, lookup_id = self.find_adapter(raw_id)
            
            if not adapter:
                # 简单ID无适配器是正常情况，直接返回
                return raw_id
            
            fetcher = adapter.get_problem_fetcher()
            if not fetcher:
                logger.debug(f"[ProblemIdResolver] 适配器 {adapter.name} 不支持题面获取")
                return raw_id
            
            parsed_id = fetcher.parse_problem_id(lookup_id)
            if not parsed_id:
                logger.debug(f"[ProblemIdResolver] 无法解析题目ID: {lookup_id}")
                return raw_id
            
            canonical = f"{adapter.name}_{parsed_id}"
            logger.debug(f"[ProblemIdResolver] {raw_id} -> {canonical}")
            return canonical
            
        except Exception as e:
            logger.warning(f"[ProblemIdResolver] 解析失败 {raw_id}: {e}")
            return raw_id
    
    def get_workspace_dir(self, raw_id: str, user_id: int) -> Path:
        """获取题目工作区目录（用户隔离，支持环境变量）
        
        Args:
            raw_id: 原始ID
            user_id: 用户ID (必须)
            
        Returns:
            工作区目录路径，如 Path("workspace/user_1/problem_shsoj_2772")
        """
        if not user_id:
            raise ValueError("user_id 是必须的参数")
        
        canonical_id = self.canonicalize(raw_id)
        safe_pid = sanitize_filename(canonical_id)
        
        # 使用环境变量或默认路径
        import os
        workspace_base = os.getenv("OJO_WORKSPACE")
        if not workspace_base:
            docker_workspace = Path("/app/workspace")
            if docker_workspace.exists():
                workspace_base = str(docker_workspace)
            else:
                workspace_base = "workspace"
        
        return Path(workspace_base) / f"user_{user_id}" / f"problem_{safe_pid}"
    
    def get_zip_path(self, raw_id: str, user_id: int) -> Path:
        """获取测试数据ZIP文件路径
        
        Args:
            raw_id: 原始ID
            user_id: 用户ID (必须)
            
        Returns:
            ZIP文件路径
        """
        pdir = self.get_workspace_dir(raw_id, user_id)
        safe_url = sanitize_filename(raw_id)
        return pdir / f"problem_{safe_url}_testcase.zip"
    
    def parse_with_adapter(self, raw_id: str) -> Tuple[Optional['OJAdapter'], Optional[str]]:
        """解析并返回适配器和题目ID
        
        Args:
            raw_id: 原始ID
            
        Returns:
            (适配器实例, 解析后的题目ID)
            如果解析失败则返回 (None, None)
        """
        try:
            adapter, lookup_id = self.find_adapter(raw_id)
            
            if not adapter:
                return None, None
            
            fetcher = adapter.get_problem_fetcher()
            if not fetcher:
                return adapter, None
            
            parsed_id = fetcher.parse_problem_id(lookup_id)
            return adapter, parsed_id
            
        except Exception as e:
            logger.warning(f"[ProblemIdResolver] 解析失败 {raw_id}: {e}")
            return None, None


# 全局单例
_global_resolver: Optional[ProblemIdResolver] = None


def get_problem_id_resolver() -> ProblemIdResolver:
    """获取全局ProblemIdResolver实例
    
    自动从配置加载默认平台设置，并使用全局适配器注册表。
    
    Returns:
        ProblemIdResolver实例
    """
    global _global_resolver
    
    if _global_resolver is None:
        from services.oj.registry import get_global_registry
        
        # 尝试从配置加载默认平台
        default_adapter = "shsoj"
        default_base_url = "https://oj.aicoders.cn"
        
        try:
            from services.unified_config import get_config
            cfg = get_config()
            default_adapter = cfg.default_oj_adapter
            default_base_url = cfg.default_oj_base_url
        except Exception as e:
            logger.debug(f"[ProblemIdResolver] 加载配置失败，使用默认值: {e}")
        
        registry = get_global_registry()
        _global_resolver = ProblemIdResolver(
            registry=registry,
            default_adapter=default_adapter,
            default_base_url=default_base_url
        )
        logger.info(f"[ProblemIdResolver] 初始化完成，默认平台: {default_adapter}")
    
    return _global_resolver


def reset_problem_id_resolver():
    """重置全局解析器 (用于测试)"""
    global _global_resolver
    _global_resolver = None
