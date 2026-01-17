"""
适配器能力定义
"""

from enum import Enum


class AdapterCapability(str, Enum):
    """适配器能力枚举（扩展版）"""
    # 基础能力
    FETCH_PROBLEM = "fetch_problem"
    UPLOAD_DATA = "upload_data"
    SUBMIT_SOLUTION = "submit_solution"
    MANAGE_TRAINING = "manage_training"
    FETCH_OFFICIAL_SOLUTION = "fetch_official_solution"
    BATCH_OPERATIONS = "batch_operations"
    
    # 高级能力
    HEALTH_CHECK = "health_check"           # 健康检查
    AUTO_RETRY = "auto_retry"               # 自动重试
    RATE_LIMITING = "rate_limiting"         # 限流
    CACHING = "caching"                     # 缓存
    AUTHENTICATION = "authentication"        # 认证管理
    
    def __str__(self):
        return self.value

