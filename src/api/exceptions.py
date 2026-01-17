# -*- coding: utf-8 -*-
"""
自定义异常类
提供细分的异常类型，便于错误处理和日志记录
"""

from typing import Optional, Dict, Any


class OJOException(Exception):
    """OJO 基础异常类"""
    
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    
    def __init__(
        self,
        message: str = "服务器内部错误",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 API 响应）"""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


# ==================== 认证相关异常 ====================

class AuthError(OJOException):
    """认证错误基类"""
    status_code = 401
    error_code = "AUTH_ERROR"


class InvalidCredentialsError(AuthError):
    """用户名或密码错误"""
    error_code = "INVALID_CREDENTIALS"
    
    def __init__(self, message: str = "用户名或密码错误"):
        super().__init__(message)


class TokenExpiredError(AuthError):
    """Token 已过期"""
    error_code = "TOKEN_EXPIRED"
    
    def __init__(self, message: str = "登录已过期，请重新登录"):
        super().__init__(message)


class TokenInvalidError(AuthError):
    """Token 无效"""
    error_code = "TOKEN_INVALID"
    
    def __init__(self, message: str = "无效的认证信息"):
        super().__init__(message)


class AccountLockedError(AuthError):
    """账户被锁定"""
    error_code = "ACCOUNT_LOCKED"
    status_code = 429
    
    def __init__(self, message: str = "账户已被锁定，请稍后重试", remaining_seconds: int = 0):
        super().__init__(message, {"remaining_seconds": remaining_seconds})


class PermissionDeniedError(AuthError):
    """权限不足"""
    status_code = 403
    error_code = "PERMISSION_DENIED"
    
    def __init__(self, message: str = "权限不足"):
        super().__init__(message)


# ==================== 适配器相关异常 ====================

class AdapterError(OJOException):
    """适配器错误基类"""
    status_code = 502
    error_code = "ADAPTER_ERROR"


class AdapterNotFoundError(AdapterError):
    """适配器未找到"""
    status_code = 404
    error_code = "ADAPTER_NOT_FOUND"
    
    def __init__(self, adapter_name: str):
        super().__init__(
            f"适配器 '{adapter_name}' 未找到",
            {"adapter": adapter_name}
        )


class AdapterConfigError(AdapterError):
    """适配器配置错误"""
    error_code = "ADAPTER_CONFIG_ERROR"
    
    def __init__(self, adapter_name: str, message: str = "适配器配置错误"):
        super().__init__(message, {"adapter": adapter_name})


class AdapterConnectionError(AdapterError):
    """适配器连接错误"""
    error_code = "ADAPTER_CONNECTION_ERROR"
    
    def __init__(self, adapter_name: str, message: str = "无法连接到目标平台"):
        super().__init__(message, {"adapter": adapter_name})


# ==================== 任务相关异常 ====================

class TaskError(OJOException):
    """任务错误基类"""
    status_code = 400
    error_code = "TASK_ERROR"


class TaskNotFoundError(TaskError):
    """任务未找到"""
    status_code = 404
    error_code = "TASK_NOT_FOUND"
    
    def __init__(self, task_id: str):
        super().__init__(
            f"任务 '{task_id}' 未找到",
            {"task_id": task_id}
        )


class TaskAlreadyExistsError(TaskError):
    """任务已存在"""
    status_code = 409
    error_code = "TASK_ALREADY_EXISTS"
    
    def __init__(self, task_id: str):
        super().__init__(
            f"任务 '{task_id}' 已存在",
            {"task_id": task_id}
        )


class TaskExecutionError(TaskError):
    """任务执行错误"""
    status_code = 500
    error_code = "TASK_EXECUTION_ERROR"


# ==================== 验证相关异常 ====================

class ValidationError(OJOException):
    """验证错误"""
    status_code = 422
    error_code = "VALIDATION_ERROR"


class PasswordWeakError(ValidationError):
    """密码强度不足"""
    error_code = "PASSWORD_WEAK"
    
    def __init__(self, message: str = "密码强度不足"):
        super().__init__(message)


class InvalidInputError(ValidationError):
    """输入无效"""
    error_code = "INVALID_INPUT"


# ==================== 资源相关异常 ====================

class ResourceError(OJOException):
    """资源错误基类"""
    status_code = 404
    error_code = "RESOURCE_ERROR"


class ResourceNotFoundError(ResourceError):
    """资源未找到"""
    error_code = "RESOURCE_NOT_FOUND"
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} '{resource_id}' 未找到",
            {"type": resource_type, "id": resource_id}
        )


class ResourceConflictError(ResourceError):
    """资源冲突"""
    status_code = 409
    error_code = "RESOURCE_CONFLICT"


# ==================== 速率限制异常 ====================

class RateLimitError(OJOException):
    """速率限制错误"""
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    
    def __init__(self, message: str = "请求过于频繁，请稍后重试", retry_after: int = 60):
        super().__init__(message, {"retry_after": retry_after})
