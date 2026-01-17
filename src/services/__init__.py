# -*- coding: utf-8 -*-
"""
OJO Services Layer v9.0

服务层统一导出模块，提供所有业务服务的单一入口。
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .auth_service import AuthService
    from .task_service import TaskService
    from .secret_service import SecretService
    from .unified_config import ConfigService


@lru_cache()
def get_auth_service() -> 'AuthService':
    """获取认证服务单例"""
    from .auth_service import get_auth_service as _get
    return _get()


@lru_cache()
def get_task_service() -> 'TaskService':
    """获取任务服务单例"""
    from .task_service import get_task_service as _get
    return _get()


@lru_cache()
def get_secret_service() -> 'SecretService':
    """获取加密服务单例"""
    from .secret_service import get_secret_service as _get
    return _get()


@lru_cache()
def get_config_service() -> 'ConfigService':
    """获取配置服务单例"""
    from .unified_config import get_config_service as _get
    return _get()


# 导出所有服务获取函数
__all__ = [
    'get_auth_service',
    'get_task_service',
    'get_secret_service',
    'get_config_service',
]
