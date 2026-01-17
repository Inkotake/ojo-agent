# -*- coding: utf-8 -*-
"""
用户上下文管理器

确保：
1. 多用户的 cookies/认证 不会相互干扰
2. 同一用户的并发任务可以共享认证信息
3. 线程安全的认证缓存
"""

import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger


@dataclass
class AuthCache:
    """认证缓存"""
    token: str
    session: Any  # requests.Session
    adapter_name: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    last_used: datetime = field(default_factory=datetime.now)
    
    def is_expired(self, has_active_tasks: bool = False) -> bool:
        """检查是否过期
        
        Args:
            has_active_tasks: 是否有活跃任务，有则不过期
        """
        # 有活跃任务时不过期
        if has_active_tasks:
            return False
        
        if self.expires_at is None:
            # 默认1小时过期
            return datetime.now() > self.created_at + timedelta(hours=1)
        return datetime.now() > self.expires_at
    
    def touch(self):
        """更新最后使用时间"""
        self.last_used = datetime.now()


@dataclass
class UserContext:
    """用户上下文 - 存储用户特定的数据"""
    user_id: int
    username: str
    
    # 认证缓存 {adapter_name: AuthCache}
    _auth_cache: Dict[str, AuthCache] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    # 用户配置
    adapter_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 任务统计
    active_tasks: int = 0
    total_tasks: int = 0
    
    def get_auth(self, adapter_name: str) -> Optional[AuthCache]:
        """获取缓存的认证（线程安全）
        
        有活跃任务时认证不会过期
        """
        with self._lock:
            auth = self._auth_cache.get(adapter_name)
            if auth and not auth.is_expired(has_active_tasks=self.active_tasks > 0):
                auth.touch()  # 更新使用时间
                return auth
            # 清理过期的（仅在无活跃任务时）
            if auth and self.active_tasks == 0:
                del self._auth_cache[adapter_name]
            return None
    
    def set_auth(self, adapter_name: str, token: str, session: Any, 
                 expires_in_hours: float = 1.0):
        """缓存认证（线程安全）"""
        with self._lock:
            self._auth_cache[adapter_name] = AuthCache(
                token=token,
                session=session,
                adapter_name=adapter_name,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=expires_in_hours)
            )
            logger.debug(f"用户 {self.username} 缓存 {adapter_name} 认证")
    
    def clear_auth(self, adapter_name: str = None):
        """清除认证缓存"""
        with self._lock:
            if adapter_name:
                self._auth_cache.pop(adapter_name, None)
            else:
                self._auth_cache.clear()
    
    def increment_task(self):
        """增加活跃任务计数"""
        with self._lock:
            self.active_tasks += 1
            self.total_tasks += 1
    
    def decrement_task(self):
        """减少活跃任务计数"""
        with self._lock:
            self.active_tasks = max(0, self.active_tasks - 1)


class UserContextManager:
    """用户上下文管理器（单例）
    
    管理所有用户的上下文，确保用户隔离
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._contexts: Dict[int, UserContext] = {}
        self._context_lock = threading.Lock()
        
        logger.info("用户上下文管理器初始化完成")
    
    def get_context(self, user_id: int, username: str = None) -> UserContext:
        """获取或创建用户上下文"""
        with self._context_lock:
            if user_id not in self._contexts:
                self._contexts[user_id] = UserContext(
                    user_id=user_id,
                    username=username or f"user_{user_id}"
                )
                logger.debug(f"创建用户上下文: {user_id}")
            return self._contexts[user_id]
    
    def remove_context(self, user_id: int):
        """移除用户上下文（用户登出时）"""
        with self._context_lock:
            if user_id in self._contexts:
                del self._contexts[user_id]
                logger.debug(f"移除用户上下文: {user_id}")
    
    def get_user_auth(self, user_id: int, adapter_name: str) -> Optional[AuthCache]:
        """获取用户的适配器认证"""
        ctx = self._contexts.get(user_id)
        if ctx:
            return ctx.get_auth(adapter_name)
        return None
    
    def set_user_auth(self, user_id: int, adapter_name: str, token: str, session: Any):
        """设置用户的适配器认证"""
        with self._context_lock:
            if user_id not in self._contexts:
                self._contexts[user_id] = UserContext(
                    user_id=user_id,
                    username=f"user_{user_id}"
                )
            self._contexts[user_id].set_auth(adapter_name, token, session)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取所有用户统计"""
        with self._context_lock:
            return {
                "total_users": len(self._contexts),
                "users": {
                    uid: {
                        "username": ctx.username,
                        "active_tasks": ctx.active_tasks,
                        "total_tasks": ctx.total_tasks,
                        "cached_auths": list(ctx._auth_cache.keys())
                    }
                    for uid, ctx in self._contexts.items()
                }
            }
    
    def cleanup_expired(self):
        """清理所有用户的过期认证"""
        with self._context_lock:
            for ctx in self._contexts.values():
                expired = [
                    name for name, auth in ctx._auth_cache.items()
                    if auth.is_expired()
                ]
                for name in expired:
                    ctx.clear_auth(name)


def get_user_context_manager() -> UserContextManager:
    """获取用户上下文管理器单例"""
    return UserContextManager()


def get_user_context(user_id: int, username: str = None) -> UserContext:
    """快捷方法：获取用户上下文"""
    return get_user_context_manager().get_context(user_id, username)
