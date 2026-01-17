# -*- coding: utf-8 -*-
"""
Repository 层 - 数据访问抽象

提供统一的数据访问接口，隔离业务逻辑与数据存储。
"""

from .user_repository import UserRepository, get_user_repository
from .task_repository import TaskRepository, get_task_repository
from .config_repository import ConfigRepository, get_config_repository

__all__ = [
    'UserRepository', 'get_user_repository',
    'TaskRepository', 'get_task_repository',
    'ConfigRepository', 'get_config_repository',
]
