# -*- coding: utf-8 -*-
"""
API 数据模型 (Pydantic Schemas) v9.0

所有 API 请求和响应的数据模型定义。
使用 Field 提供字段描述，增强 API 文档。
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# ==================== 认证相关 ====================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=4, description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    token: str = Field(..., description="JWT Token")
    user: Dict[str, Any] = Field(..., description="用户信息")


class UserInfo(BaseModel):
    """用户信息"""
    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    role: Literal["user", "admin"] = Field(..., description="角色")
    email: Optional[str] = Field(None, description="邮箱")
    status: Literal["active", "disabled"] = Field("active", description="状态")


# ==================== 任务相关 ====================

class ProblemWithAdapter(BaseModel):
    """带适配器的题目信息"""
    id: str = Field(..., description="题目ID或URL")
    adapter: str = Field("auto", description="拉取适配器名称")


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    problem_ids: List[str] = Field(default=[], description="题目ID列表（兼容旧格式）")
    problems: Optional[List[ProblemWithAdapter]] = Field(None, description="题目列表（新格式，每个题目带适配器）")
    enable_fetch: bool = Field(True, description="启用题目拉取")
    enable_generation: bool = Field(True, description="启用数据生成")
    enable_upload: bool = Field(True, description="启用题目上传")
    enable_solve: bool = Field(True, description="启用代码求解")
    source_adapter: Optional[str] = Field(None, description="源OJ适配器（旧格式）")
    target_adapter: Optional[str] = Field(None, description="目标OJ适配器")
    llm_provider: Optional[str] = Field("deepseek", description="统一LLM提供商（生成+求解）")


class TaskResponse(BaseModel):
    """任务响应"""
    id: int = Field(..., description="任务ID")
    problem_id: str = Field(..., description="题目ID")
    status: int = Field(..., description="状态: 0=等待, 1=运行, 4=成功, -1=失败")
    stage: Optional[str] = Field(None, description="当前阶段")
    progress: int = Field(0, ge=0, le=100, description="进度(0-100)")
    source_oj: Optional[str] = Field(None, description="源OJ")
    target_oj: Optional[str] = Field(None, description="目标OJ")
    uploaded_url: Optional[str] = Field(None, description="上传后的URL")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: Optional[str] = Field(None, description="创建时间")


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., ge=0, description="总数")


# ==================== 配置相关 ====================

class ConfigUpdateRequest(BaseModel):
    """更新配置请求"""
    scope: Literal["user", "system"] = Field("user", description="配置范围")
    key: str = Field(..., description="配置键")
    value: Any = Field(..., description="配置值")


class AdapterConfigRequest(BaseModel):
    """适配器配置请求"""
    config: Dict[str, Any] = Field(..., description="适配器配置")


# ==================== 管理员相关 ====================

class CreateUserRequest(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=4, description="密码")
    role: Literal["user", "admin"] = Field("user", description="角色")
    email: Optional[str] = Field(None, description="邮箱")


class UpdateUserRoleRequest(BaseModel):
    """更新用户角色请求"""
    role: Literal["user", "admin"] = Field(..., description="新角色")


# ==================== 通用响应 ====================

class SuccessResponse(BaseModel):
    """通用成功响应"""
    status: Literal["success"] = Field("success", description="状态")
    message: str = Field(..., description="消息")


class ErrorResponse(BaseModel):
    """通用错误响应"""
    status: Literal["error"] = Field("error", description="状态")
    detail: str = Field(..., description="错误详情")


class StatsResponse(BaseModel):
    """统计响应"""
    total: int = Field(..., ge=0, description="总任务数")
    success: int = Field(..., ge=0, description="成功数")
    running: int = Field(..., ge=0, description="运行中数")
    failed: int = Field(..., ge=0, description="失败数")
    pending: int = Field(..., ge=0, description="等待中数")
