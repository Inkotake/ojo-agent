"""
配置中心实现
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from loguru import logger

from .types import ConfigScope, ConfigEntry


class ConfigCenter:
    """
    统一配置中心
    支持多层级配置（系统、适配器、用户等）
    """
    
    def __init__(self):
        self._configs: Dict[str, Dict[str, Any]] = {
            scope.value: {} for scope in ConfigScope
        }
        self._entries: Dict[str, ConfigEntry] = {}
    
    def set(self, key: str, value: Any, scope: ConfigScope = ConfigScope.USER) -> None:
        """
        设置配置
        
        Args:
            key: 配置键（支持点分隔的层级，如 "adapter.shsoj.base_url"）
            value: 配置值
            scope: 配置作用域
        """
        scope_key = scope.value if isinstance(scope, ConfigScope) else scope
        
        # 解析层级键
        keys = key.split('.')
        current = self._configs[scope_key]
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
        
        logger.debug(f"设置配置: {scope_key}.{key} = {value}")
    
    def get(self, key: str, scope: ConfigScope = None, default: Any = None) -> Any:
        """
        获取配置
        
        Args:
            key: 配置键
            scope: 配置作用域（None表示按优先级搜索所有作用域）
            default: 默认值
        
        Returns:
            配置值
        """
        if scope is not None:
            # 指定作用域
            scope_key = scope.value if isinstance(scope, ConfigScope) else scope
            return self._get_from_scope(key, scope_key, default)
        
        # 按优先级搜索：USER > PIPELINE > ADAPTER > LLM > SYSTEM
        search_order = [
            ConfigScope.USER,
            ConfigScope.PIPELINE,
            ConfigScope.ADAPTER,
            ConfigScope.LLM,
            ConfigScope.SYSTEM,
        ]
        
        for s in search_order:
            value = self._get_from_scope(key, s.value, None)
            if value is not None:
                return value
        
        return default
    
    def _get_from_scope(self, key: str, scope_key: str, default: Any) -> Any:
        """从指定作用域获取配置"""
        keys = key.split('.')
        current = self._configs.get(scope_key, {})
        
        for k in keys:
            if not isinstance(current, dict) or k not in current:
                return default
            current = current[k]
        
        return current
    
    def get_adapter_config(self, adapter_name: str) -> Dict[str, Any]:
        """
        获取适配器配置
        
        Args:
            adapter_name: 适配器名称
        
        Returns:
            适配器配置字典
        """
        return self.get(adapter_name, scope=ConfigScope.ADAPTER, default={})
    
    def set_adapter_config(self, adapter_name: str, config: Dict[str, Any]) -> None:
        """设置适配器配置"""
        self.set(adapter_name, config, scope=ConfigScope.ADAPTER)
    
    def get_llm_config(self, provider: str, task_type: str = None) -> Dict[str, Any]:
        """
        获取LLM配置
        
        Args:
            provider: Provider名称（如 "deepseek"）
            task_type: 任务类型（如 "generation"）
        
        Returns:
            LLM配置字典
        """
        if task_type:
            key = f"{provider}.{task_type}"
        else:
            key = provider
        
        return self.get(key, scope=ConfigScope.LLM, default={})
    
    def load_from_file(self, config_file: Path) -> None:
        """
        从配置文件加载
        
        Args:
            config_file: 配置文件路径
        """
        if not config_file.exists():
            logger.warning(f"配置文件不存在: {config_file}")
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 解析并加载配置
            self._parse_and_load(config_data)
            
            logger.info(f"配置加载成功: {config_file}")
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
    
    def _parse_and_load(self, config_data: Dict[str, Any]) -> None:
        """解析并加载配置数据"""
        # 适配器配置
        for key in ['oj_base_url', 'oj_username', 'oj_password', 
                    'default_oj_adapter', 'default_oj_base_url']:
            if key in config_data:
                # 解析为适配器配置
                adapter_key = key.replace('oj_', '').replace('default_', '')
                self.set(f"default.{adapter_key}", config_data[key], ConfigScope.ADAPTER)
        
        # LLM配置
        llm_keys = [k for k in config_data.keys() if any(
            k.startswith(prefix) for prefix in [
                'deepseek_', 'gemini_', 'siliconflow_', 
                'llm_provider_', 'temperature_', 'top_p_'
            ]
        )]
        for key in llm_keys:
            self.set(key, config_data[key], ConfigScope.LLM)
        
        # 系统配置
        system_keys = [
            'llm_max_concurrency', 'oj_max_concurrency', 'max_workers',
            'request_timeout_minutes', 'code_exec_timeout_minutes',
            'enable_solution_search', 'enable_search_summary',
            'enable_global_rate_limit_gate', 'enable_incremental_regen',
            'proxy_enabled', 'http_proxy', 'https_proxy', 'verify_ssl',
            'log_level', 'theme'
        ]
        for key in system_keys:
            if key in config_data:
                self.set(key, config_data[key], ConfigScope.SYSTEM)
        
        # Pipeline配置
        pipeline_keys = [
            'training_group_id', 'training_rank', 'training_category_id',
            'training_auth', 'training_private_pwd', 'training_author'
        ]
        for key in pipeline_keys:
            if key in config_data:
                self.set(key, config_data[key], ConfigScope.PIPELINE)
    
    def save_to_file(self, config_file: Path) -> None:
        """
        保存配置到文件
        
        Args:
            config_file: 配置文件路径
        """
        try:
            # 合并所有配置
            merged_config = {}
            for scope_key, scope_config in self._configs.items():
                self._flatten_dict(scope_config, merged_config)
            
            # 写入文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(merged_config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置保存成功: {config_file}")
        except Exception as e:
            logger.error(f"配置保存失败: {e}")
    
    def _flatten_dict(self, nested: Dict, flat: Dict, prefix: str = "") -> None:
        """将嵌套字典扁平化"""
        for key, value in nested.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._flatten_dict(value, flat, full_key)
            else:
                flat[full_key] = value
    
    def register_entry(self, entry: ConfigEntry) -> None:
        """注册配置条目（用于验证和文档）"""
        self._entries[entry.key] = entry
    
    def validate(self) -> List[str]:
        """
        验证配置
        
        Returns:
            错误列表（空列表表示验证通过）
        """
        errors = []
        for key, entry in self._entries.items():
            value = self.get(entry.key, entry.scope)
            if not entry.validate():
                errors.append(f"配置验证失败: {entry.scope}.{entry.key}")
        return errors
    
    def get_all(self, scope: ConfigScope = None) -> Dict[str, Any]:
        """获取所有配置"""
        if scope is not None:
            scope_key = scope.value if isinstance(scope, ConfigScope) else scope
            return self._configs.get(scope_key, {}).copy()
        
        # 返回所有配置
        return {
            scope_key: config.copy() 
            for scope_key, config in self._configs.items()
        }


# 全局配置中心实例
_global_config_center: ConfigCenter = None


def get_config_center() -> ConfigCenter:
    """获取全局配置中心实例"""
    global _global_config_center
    if _global_config_center is None:
        _global_config_center = ConfigCenter()
    return _global_config_center

