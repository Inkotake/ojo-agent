# -*- coding: utf-8 -*-
"""
配置数据仓库
"""

from typing import Optional, Dict, Any
from loguru import logger


class ConfigRepository:
    """配置数据访问层"""
    
    def __init__(self, db=None):
        self._db = db
    
    @property
    def db(self):
        if self._db is None:
            from core.database import get_database
            self._db = get_database()
        return self._db
    
    # ==================== 系统配置 ====================
    
    def get_system_config(self, key: str, default: Any = None) -> Any:
        """获取系统配置"""
        return self.db.get_system_config(key, default)
    
    def set_system_config(self, key: str, value: Any) -> bool:
        """设置系统配置"""
        self.db.set_system_config(key, value)
        return True
    
    def get_all_system_configs(self) -> Dict[str, Any]:
        """获取所有系统配置"""
        return self.db.get_all_system_configs()
    
    # ==================== 用户配置 ====================
    
    def get_user_config(self, user_id: int, key: str = None) -> Any:
        """获取用户配置"""
        configs = self.db.get_user_config(user_id)
        if key:
            for cfg in configs:
                if cfg.get("key") == key:
                    return cfg.get("value")
            return None
        return configs
    
    def set_user_config(self, user_id: int, platform: str, 
                        cookie: str = None, token: str = None) -> bool:
        """设置用户配置"""
        self.db.save_user_config(user_id, platform, cookie, token)
        return True
    
    # ==================== 适配器配置 ====================
    
    def get_adapter_config(self, user_id: int, adapter_name: str) -> Dict[str, Any]:
        """获取用户的适配器配置"""
        return self.db.get_user_adapter_config(user_id, adapter_name)
    
    def set_adapter_config(self, user_id: int, adapter_name: str, 
                           config: Dict[str, Any]) -> bool:
        """设置用户的适配器配置"""
        self.db.save_user_adapter_config(user_id, adapter_name, config)
        return True
    
    def get_all_adapter_configs(self, user_id: int) -> Dict[str, Dict[str, Any]]:
        """获取用户的所有适配器配置"""
        return self.db.get_all_user_adapter_configs(user_id)
    
    # ==================== 模块设置 ====================
    
    def get_module_settings(self, user_id: int) -> Dict[str, Any]:
        """获取用户的模块设置"""
        return self.db.get_user_module_settings(user_id)
    
    def set_module_settings(self, user_id: int, settings: Dict[str, Any]) -> bool:
        """设置用户的模块设置"""
        self.db.save_user_module_settings(user_id, settings)
        return True


# 单例
_config_repo: Optional[ConfigRepository] = None


def get_config_repository() -> ConfigRepository:
    """获取配置仓库实例"""
    global _config_repo
    if _config_repo is None:
        _config_repo = ConfigRepository()
    return _config_repo
