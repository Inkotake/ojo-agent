# -*- coding: utf-8 -*-
"""
配置验证模块
启动时验证必要配置的完整性
"""

import os
from typing import List, Tuple, Optional
from pathlib import Path
from loguru import logger


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        验证所有配置
        
        Returns:
            (是否通过, 错误列表, 警告列表)
        """
        self.errors = []
        self.warnings = []
        
        # 验证各项配置
        self._validate_paths()
        self._validate_database()
        self._validate_security()
        self._validate_llm()
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_paths(self) -> None:
        """验证必要路径"""
        # 工作目录
        workspace = os.getenv("OJO_WORKSPACE", "workspace")
        if not os.path.exists(workspace):
            try:
                os.makedirs(workspace, exist_ok=True)
                logger.info(f"创建工作目录: {workspace}")
            except Exception as e:
                self.errors.append(f"无法创建工作目录 {workspace}: {e}")
        
        # 日志目录
        logs_dir = os.getenv("OJO_LOGS_DIR", "logs")
        if not os.path.exists(logs_dir):
            try:
                os.makedirs(logs_dir, exist_ok=True)
            except Exception:
                self.warnings.append(f"无法创建日志目录 {logs_dir}，将使用默认位置")
    
    def _validate_database(self) -> None:
        """验证数据库配置"""
        db_path = os.getenv("OJO_DB_PATH", "ojo.db")
        db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else "."
        
        if not os.path.exists(db_dir):
            self.warnings.append(f"数据库目录不存在: {db_dir}")
        
        # 检查数据库文件权限
        if os.path.exists(db_path):
            if not os.access(db_path, os.R_OK | os.W_OK):
                self.errors.append(f"数据库文件权限不足: {db_path}")
    
    def _validate_security(self) -> None:
        """验证安全配置"""
        # JWT 密钥
        jwt_key = os.getenv("JWT_SECRET_KEY")
        if not jwt_key:
            self.warnings.append("未设置 JWT_SECRET_KEY 环境变量，将使用数据库存储或随机生成")
        
        # CORS 配置
        cors_origins = os.getenv("CORS_ORIGINS")
        debug_mode = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
        
        if not cors_origins and not debug_mode:
            self.warnings.append("生产环境未设置 CORS_ORIGINS，建议配置允许的域名列表")
    
    def _validate_llm(self) -> None:
        """验证 LLM 配置"""
        # 检查是否至少配置了一个 LLM provider
        providers = {
            "deepseek": os.getenv("DEEPSEEK_API_KEY"),
            "gemini": os.getenv("GEMINI_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "siliconflow": os.getenv("SILICONFLOW_API_KEY"),
        }
        
        configured_providers = [k for k, v in providers.items() if v]
        
        if not configured_providers:
            self.warnings.append(
                "未配置任何 LLM API 密钥 (DEEPSEEK_API_KEY, GEMINI_API_KEY 等)，"
                "请在 config.json 或环境变量中配置"
            )
        else:
            logger.info(f"已配置的 LLM 提供商: {', '.join(configured_providers)}")


def validate_config_on_startup() -> bool:
    """
    启动时验证配置
    
    Returns:
        是否验证通过
    """
    validator = ConfigValidator()
    is_valid, errors, warnings = validator.validate_all()
    
    # 输出警告
    for warning in warnings:
        logger.warning(f"[配置警告] {warning}")
    
    # 输出错误
    for error in errors:
        logger.error(f"[配置错误] {error}")
    
    if is_valid:
        logger.info("配置验证通过")
    else:
        logger.error(f"配置验证失败，共 {len(errors)} 个错误")
    
    return is_valid


# 便捷导出
__all__ = ['ConfigValidator', 'validate_config_on_startup']
