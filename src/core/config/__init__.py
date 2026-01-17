"""
配置系统模块 (DEPRECATED)

!!! DEPRECATED !!!
此模块已弃用，请使用 services.unified_config.ConfigService。
保留此文件仅为向后兼容。

推荐使用:
    from services.unified_config import get_config, update_config
"""

import warnings
warnings.warn(
    "core.config 已弃用，请使用 services.unified_config",
    DeprecationWarning,
    stacklevel=2
)

from .center import ConfigCenter, get_config_center
from .types import ConfigScope, ConfigEntry
from .validation import ConfigValidator, validate_config_on_startup

__all__ = [
    "ConfigCenter",
    "get_config_center",
    "ConfigScope",
    "ConfigEntry",
    "ConfigValidator",
    "validate_config_on_startup",
]

