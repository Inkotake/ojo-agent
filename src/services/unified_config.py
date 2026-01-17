# -*- coding: utf-8 -*-
"""
统一配置管理服务 v3.0

唯一配置源：数据库 (system_configs 表)
- 普通配置存储在 app_config key 中（JSON 格式）
- API Key 等敏感信息单独加密存储（独立 key）

config.json 仅用于首次初始化迁移，运行时完全依赖数据库。

使用方式：
    from services.unified_config import get_config, update_config
    
    cfg = get_config()
    update_config(oj_base_url="https://new.oj.com")
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, asdict, field, fields
from pathlib import Path
from typing import Optional, Dict, Any, List

from loguru import logger


# API Key 字段列表（这些字段需要从加密存储中读取）
API_KEY_FIELDS = [
    'deepseek_api_key',
    'deepseek_api_key_siliconflow',
    'openai_api_key',
]


@dataclass
class AppConfig:
    """应用配置（唯一定义）"""
    # OJ配置
    oj_base_url: str = "https://oj-api.shsbnu.net"
    oj_username: str = ""
    oj_password: str = ""
    default_oj_adapter: str = "shsoj"
    default_oj_base_url: str = "https://oj.aicoders.cn"

    # DeepSeek配置
    deepseek_api_key: str = ""
    deepseek_api_key_siliconflow: str = ""
    deepseek_model: str = "deepseek-reasoner"  # 统一模型（生成+求解）
    deepseek_model_summary: str = "deepseek-chat"
    deepseek_api_url: str = "https://api.deepseek.com/v1"
    # NOTE: deepseek_model_generation 和 deepseek_model_solution 已废弃
    # 现在统一使用 deepseek_model
    
    # OpenAI 兼容配置
    openai_api_key: str = ""
    openai_api_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"
    
    # NOTE: Gemini 已移除，如需使用可通过 OpenAI 兼容模式
    # 以下字段保留以兼容旧数据库配置，但不再使用
    # gemini_api_key: str = ""  # 已废弃
    # gemini_model: str = ""    # 已废弃
    
    # SiliconFlow配置
    siliconflow_model_ocr: str = "deepseek-ai/DeepSeek-OCR"
    siliconflow_api_url: str = "https://api.siliconflow.cn/v1"
    
    # LLM Provider选择
    llm_provider_ocr: str = "siliconflow"
    llm_provider_summary: str = "deepseek"  # 使用 deepseek-chat 模型
    
    # 废弃字段（保留以兼容旧数据，但不再使用）
    # NOTE: llm_provider_generation 和 llm_provider_solution 已废弃
    # 现在用户在任务界面选择统一的 llm_provider，生成和求解使用同一个
    llm_provider_generation: str = "deepseek"  # 废弃，仅兼容
    llm_provider_solution: str = "deepseek"  # 废弃，仅兼容
    
    # 题解搜索配置
    solution_source: str = "search"
    enable_solution_search: bool = True
    enable_search_summary: bool = True
    
    # LLM参数
    temperature_generation: float = 0.7
    temperature_solution: float = 0.7
    temperature_ocr: float = 0.2
    temperature_summary: float = 0.3
    top_p_generation: float = 0.9
    top_p_solution: float = 0.9
    top_p_ocr: float = 0.8
    top_p_summary: float = 0.9
    thinking_budget: int = 16384
    max_output_tokens: int = 65536

    # 并发和超时
    llm_max_concurrency: int = 2
    oj_max_concurrency: int = 2
    max_workers: int = 10
    request_timeout_minutes: int = 5
    code_exec_timeout_minutes: int = 5
    theme: str = "auto"

    # 代理 & SSL
    proxy_enabled: bool = False
    http_proxy: str = ""
    https_proxy: str = ""
    verify_ssl: bool = True

    # 日志级别
    log_level: str = "INFO"

    # 流程优化
    enable_global_rate_limit_gate: bool = False
    enable_incremental_regen: bool = False

    # 题单配置
    training_group_id: int = 3609
    training_rank: int = 1000
    training_category_id: Optional[int] = None
    training_auth: str = "Public"
    training_private_pwd: str = ""
    training_author: str = ""
    
    # 适配器配置
    adapter_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    module_adapter_settings: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'fetch': {'mode': 'auto'},
        'upload': {'mode': 'manual', 'adapter': 'shsoj'},
        'submit': {'mode': 'manual', 'adapter': 'shsoj'}
    })


class ConfigService:
    """配置服务（单例）- 使用数据库作为唯一配置源"""
    
    _instance: Optional['ConfigService'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._config: Optional[AppConfig] = None
        self._db = None
        self._config_lock = threading.Lock()
        self._initialized = True
        self._init_config()
    
    def _init_config(self):
        """初始化配置"""
        try:
            from core.database import get_database
            self._db = get_database()
        except Exception as e:
            logger.warning(f"[Config] 数据库不可用: {e}")
            self._db = None
        
        self._load()
    
    def _load(self):
        """从数据库加载配置
        
        加载顺序：
        1. 从 app_config 加载基础配置（JSON 格式）
        2. 从独立 key 加载加密的 API Key 并合并
        """
        with self._config_lock:
            default = asdict(AppConfig())
            
            if self._db:
                try:
                    db_config = self._db.get_system_config("app_config")
                    if db_config and isinstance(db_config, dict):
                        default.update(db_config)
                except Exception as e:
                    logger.debug(f"[Config] 读取数据库失败: {e}")
            
            # 如果数据库没有配置，尝试从 config.json 初始化（仅首次）
            if not self._db or not self._db.get_system_config("app_config"):
                self._migrate_from_file()
                if self._db:
                    try:
                        db_config = self._db.get_system_config("app_config")
                        if db_config:
                            default.update(db_config)
                    except:
                        pass
            
            # 过滤掉 AppConfig 中不存在的字段（兼容旧数据库配置）
            valid_fields = {f.name for f in fields(AppConfig)}
            filtered_default = {k: v for k, v in default.items() if k in valid_fields}
            
            # 记录被过滤的废弃字段
            deprecated_fields = set(default.keys()) - valid_fields
            if deprecated_fields:
                logger.debug(f"[Config] 过滤废弃字段: {deprecated_fields}")
            
            self._config = AppConfig(**filtered_default)
            
            # 关键：从加密存储加载 API Key 并合并
            self._load_encrypted_api_keys()
    
    def _load_encrypted_api_keys(self):
        """从数据库加载加密存储的 API Key
        
        API Key 单独加密存储在 system_configs 表中，
        需要解密后合并到 AppConfig 中。
        """
        if not self._db:
            return
        
        try:
            from services.secret_service import get_secret_service
            secret_service = get_secret_service()
            
            cursor = self._db.conn.cursor()
            
            for key_field in API_KEY_FIELDS:
                try:
                    cursor.execute(
                        "SELECT value FROM system_configs WHERE key = ?",
                        (key_field,)
                    )
                    row = cursor.fetchone()
                    
                    if row and row[0]:
                        try:
                            decrypted = secret_service.decrypt(row[0])
                            if decrypted:
                                setattr(self._config, key_field, decrypted)
                                logger.debug(f"[Config] 已加载加密字段: {key_field}")
                        except Exception as e:
                            logger.debug(f"[Config] 解密 {key_field} 失败: {e}")
                except Exception as e:
                    logger.debug(f"[Config] 读取 {key_field} 失败: {e}")
                    
        except Exception as e:
            logger.warning(f"[Config] 加载加密 API Key 失败: {e}")
    
    def _migrate_from_file(self):
        """从 config.json 迁移到数据库（首次运行）"""
        # 尝试多个可能的路径
        possible_paths = [
            Path("config.json"),
            Path(__file__).parent.parent.parent / "config.json",  # 项目根目录
            Path.cwd() / "config.json",
        ]
        
        config_path = None
        for p in possible_paths:
            if p.exists():
                config_path = p
                break
        
        if not config_path:
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            
            if self._db:
                self._db.set_system_config("app_config", file_config)
                logger.info("[Config] 已从 config.json 迁移配置到数据库")
        except Exception as e:
            logger.warning(f"[Config] 迁移失败: {e}")
    
    @property
    def cfg(self) -> AppConfig:
        """获取配置"""
        if self._config is None:
            self._load()
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取单个配置项"""
        return getattr(self.cfg, key, default)
    
    def update(self, **kwargs) -> AppConfig:
        """更新配置并保存到数据库
        
        API Key 字段会被加密后单独存储，
        其他字段保存到 app_config JSON 中。
        """
        with self._config_lock:
            api_keys_to_save = {}
            
            for key, value in kwargs.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
                    
                    # API Key 需要单独加密保存
                    if key in API_KEY_FIELDS and value:
                        api_keys_to_save[key] = value
                else:
                    logger.warning(f"[Config] 未知配置项: {key}")
            
            # 保存普通配置到 app_config
            self._save()
            
            # 加密保存 API Key
            if api_keys_to_save:
                self._save_encrypted_api_keys(api_keys_to_save)
            
            return self._config
    
    def _save_encrypted_api_keys(self, api_keys: Dict[str, str]):
        """加密保存 API Key 到数据库"""
        if not self._db:
            return
        
        try:
            from services.secret_service import get_secret_service
            secret_service = get_secret_service()
            
            for key, value in api_keys.items():
                if value:
                    encrypted = secret_service.encrypt(value)
                    self._db.set_system_config(key, encrypted)
                    logger.info(f"[Config] 已加密保存: {key}")
        except Exception as e:
            logger.error(f"[Config] 加密保存 API Key 失败: {e}")
    
    def _save(self):
        """保存配置到数据库
        
        注意：API Key 字段不会保存到 app_config JSON 中，
        它们单独加密存储。
        """
        if self._db:
            try:
                config_dict = asdict(self._config)
                
                # 从 app_config 中移除 API Key 字段（它们单独加密存储）
                for key in API_KEY_FIELDS:
                    config_dict.pop(key, None)
                
                self._db.set_system_config("app_config", config_dict)
            except Exception as e:
                logger.error(f"[Config] 保存失败: {e}")
    
    def reload(self) -> AppConfig:
        """重新加载配置"""
        self._load()
        return self._config
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return asdict(self.cfg)
    
    def export_to_file(self, path: Path = None):
        """导出配置到文件"""
        path = path or Path("config.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.cfg), f, ensure_ascii=False, indent=2)
        logger.info(f"[Config] 已导出到 {path}")


# ==================== 全局访问函数 ====================

_service: Optional[ConfigService] = None

def get_config_service() -> ConfigService:
    """获取配置服务实例"""
    global _service
    if _service is None:
        _service = ConfigService()
    return _service

def get_config() -> AppConfig:
    """获取配置"""
    return get_config_service().cfg

def update_config(**kwargs) -> AppConfig:
    """更新配置"""
    return get_config_service().update(**kwargs)

def reload_config() -> AppConfig:
    """重新加载配置"""
    return get_config_service().reload()


# ==================== 兼容旧代码 ====================

# 兼容 config_manager.py 的接口
class ConfigManager:
    """兼容层 - 转发到 ConfigService"""
    
    def __init__(self, path: Path = None):
        self._service = get_config_service()
    
    @property
    def cfg(self) -> AppConfig:
        return self._service.cfg
    
    @cfg.setter
    def cfg(self, value: AppConfig):
        self._service._config = value
        self._service._save()
    
    def load_or_init(self):
        self._service.reload()
    
    def save(self):
        self._service._save()


# 兼容 config_singleton.py 的接口
def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    """兼容旧接口"""
    return ConfigManager(config_path)

def save_config():
    """兼容旧接口"""
    get_config_service()._save()
