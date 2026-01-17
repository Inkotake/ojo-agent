# -*- coding: utf-8 -*-
"""Manual适配器"""

from typing import Dict, Any, Set, Optional
from pathlib import Path

from ...base.adapter_base import OJAdapter
from ...base.capabilities import OJCapability
from ...base.problem_fetcher import ProblemFetcher
from .problem_fetcher_impl import ManualProblemFetcher


class ManualAdapter(OJAdapter):
    """手动题面适配器
    
    用于处理用户手动粘贴的题面，支持从本地缓存读取已格式化的题面数据
    """
    
    def __init__(self, workspace_dir: Path = None):
        super().__init__()
        self._problem_fetcher = None
        # workspace_dir 应该是用户隔离的工作区 (如 workspace/user_1)
        if workspace_dir:
            self.workspace_dir = workspace_dir
        else:
            # 支持环境变量
            import os
            workspace_base = os.getenv("OJO_WORKSPACE")
            if not workspace_base:
                docker_workspace = Path("/app/workspace")
                if docker_workspace.exists():
                    workspace_base = str(docker_workspace)
                else:
                    workspace_base = "workspace"
            self.workspace_dir = Path(workspace_base)
    
    def set_workspace_dir(self, workspace_dir: Path):
        """设置工作区目录（用于用户隔离）"""
        self.workspace_dir = workspace_dir
        # 重置 problem_fetcher 以使用新的 workspace_dir
        self._problem_fetcher = None
    
    @property
    def name(self) -> str:
        return "manual"
    
    @property
    def display_name(self) -> str:
        return "手动题面"
    
    @property
    def capabilities(self) -> Set[OJCapability]:
        """支持拉取题面"""
        return {OJCapability.FETCH_PROBLEM}
    
    def get_problem_fetcher(self) -> ProblemFetcher:
        """返回题面获取器"""
        if not self._problem_fetcher:
            self._problem_fetcher = ManualProblemFetcher(self.workspace_dir)
        return self._problem_fetcher
    
    def get_config_schema(self) -> Dict[str, Any]:
        """无需配置"""
        return {}
    
    def validate_config(self, config: Dict[str, str]) -> tuple[bool, Optional[str]]:
        """验证配置（总是成功）"""
        return True, None

