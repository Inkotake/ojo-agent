# -*- coding: utf-8 -*-
"""
并发限制管理器

管理系统各环节的并发限制：
- 全局任务并发数
- 每用户任务并发数
- 每适配器功能并发数 (fetch/upload/solve等)
- LLM请求并发数

所有配置持久化到数据库，系统重启后恢复
"""

import asyncio
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
from contextlib import contextmanager
import time


@dataclass
class ConcurrencyConfig:
    """并发配置"""
    # 全局限制
    max_global_tasks: int = 50           # 全局最大并发任务数
    max_tasks_per_user: int = 10         # 每用户最大并发任务数
    
    # 适配器限制 (按功能)
    max_fetch_concurrent: int = 10       # 拉取题目并发数
    max_upload_concurrent: int = 5       # 上传数据并发数
    max_solve_concurrent: int = 5        # 求解并发数
    
    # LLM限制
    max_llm_concurrent: int = 8          # LLM请求并发数
    max_llm_per_provider: int = 4        # 每个Provider并发数
    
    # 本地编译验题限制
    max_compile_concurrent: int = 2      # 本地编译验题并发数（限制CPU占用）
    
    # 队列限制
    max_queue_size: int = 500            # 最大队列长度
    task_timeout_seconds: int = 600      # 任务超时时间 (10分钟)


@dataclass 
class SemaphoreStats:
    """信号量统计"""
    name: str
    max_count: int
    current_count: int = 0
    waiting_count: int = 0
    total_acquired: int = 0
    total_released: int = 0


class ManagedSemaphore:
    """带统计的信号量"""
    
    def __init__(self, name: str, max_count: int):
        self.name = name
        self.max_count = max_count
        self._semaphore = threading.Semaphore(max_count)
        self._lock = threading.Lock()
        self._current = 0
        self._waiting = 0
        self._total_acquired = 0
        self._total_released = 0
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """获取信号量"""
        with self._lock:
            self._waiting += 1
        
        try:
            result = self._semaphore.acquire(blocking=blocking, timeout=timeout)
            if result:
                with self._lock:
                    self._current += 1
                    self._total_acquired += 1
            return result
        finally:
            with self._lock:
                self._waiting -= 1
    
    def release(self):
        """释放信号量"""
        self._semaphore.release()
        with self._lock:
            self._current -= 1
            self._total_released += 1
    
    def get_stats(self) -> SemaphoreStats:
        """获取统计信息"""
        with self._lock:
            return SemaphoreStats(
                name=self.name,
                max_count=self.max_count,
                current_count=self._current,
                waiting_count=self._waiting,
                total_acquired=self._total_acquired,
                total_released=self._total_released
            )
    
    def resize(self, new_max: int):
        """调整信号量大小"""
        if new_max == self.max_count:
            return
        
        diff = new_max - self.max_count
        self.max_count = new_max
        
        if diff > 0:
            # 增加容量
            for _ in range(diff):
                self._semaphore.release()
        elif diff < 0:
            # 减少容量 (立即获取多余的许可)
            for _ in range(-diff):
                self._semaphore.acquire(blocking=False)
    
    @contextmanager
    def acquire_context(self, timeout: Optional[float] = None):
        """上下文管理器方式获取"""
        acquired = self.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"获取 {self.name} 信号量超时")
        try:
            yield
        finally:
            self.release()


class ConcurrencyManager:
    """并发限制管理器 (单例)"""
    
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
        self.config = ConcurrencyConfig()
        self._semaphores: Dict[str, ManagedSemaphore] = {}
        self._user_semaphores: Dict[int, ManagedSemaphore] = {}
        self._adapter_semaphores: Dict[str, ManagedSemaphore] = {}
        
        # 初始化全局信号量
        self._init_semaphores()
        
        # 从数据库加载配置
        self._load_config_from_db()
        
        logger.info("并发管理器初始化完成")
    
    def _init_semaphores(self):
        """初始化信号量"""
        self._semaphores = {
            "global_tasks": ManagedSemaphore("全局任务", self.config.max_global_tasks),
            "fetch": ManagedSemaphore("拉取", self.config.max_fetch_concurrent),
            "upload": ManagedSemaphore("上传", self.config.max_upload_concurrent),
            "solve": ManagedSemaphore("求解", self.config.max_solve_concurrent),
            "llm": ManagedSemaphore("LLM", self.config.max_llm_concurrent),
            "compile": ManagedSemaphore("本地编译", self.config.max_compile_concurrent),
        }
    
    def _load_config_from_db(self):
        """从数据库加载配置"""
        try:
            from core.database import get_database
            db = get_database()
            
            # 加载并发配置
            config_data = db.get_system_config("concurrency_config")
            if config_data:
                import json
                # 处理可能是字符串或已解析的dict的情况
                if isinstance(config_data, str):
                    config_dict = json.loads(config_data)
                elif isinstance(config_data, dict):
                    config_dict = config_data
                else:
                    config_dict = {}
                
                for key, value in config_dict.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                
                # 更新信号量大小
                self._update_semaphore_sizes()
                logger.info(f"从数据库加载并发配置: {config_dict}")
        except Exception as e:
            logger.warning(f"加载并发配置失败，使用默认值: {e}")
    
    def _update_semaphore_sizes(self):
        """更新信号量大小"""
        self._semaphores["global_tasks"].resize(self.config.max_global_tasks)
        self._semaphores["fetch"].resize(self.config.max_fetch_concurrent)
        self._semaphores["upload"].resize(self.config.max_upload_concurrent)
        self._semaphores["solve"].resize(self.config.max_solve_concurrent)
        self._semaphores["llm"].resize(self.config.max_llm_concurrent)
        self._semaphores["compile"].resize(self.config.max_compile_concurrent)
    
    def save_config(self):
        """保存配置到数据库"""
        try:
            from core.database import get_database
            import json
            
            db = get_database()
            config_dict = {
                "max_global_tasks": self.config.max_global_tasks,
                "max_tasks_per_user": self.config.max_tasks_per_user,
                "max_fetch_concurrent": self.config.max_fetch_concurrent,
                "max_upload_concurrent": self.config.max_upload_concurrent,
                "max_solve_concurrent": self.config.max_solve_concurrent,
                "max_llm_concurrent": self.config.max_llm_concurrent,
                "max_llm_per_provider": self.config.max_llm_per_provider,
                "max_compile_concurrent": self.config.max_compile_concurrent,
                "max_queue_size": self.config.max_queue_size,
                "task_timeout_seconds": self.config.task_timeout_seconds,
            }
            
            db.set_system_config("concurrency_config", json.dumps(config_dict))
            self._update_semaphore_sizes()
            logger.info(f"并发配置已保存: {config_dict}")
        except Exception as e:
            logger.error(f"保存并发配置失败: {e}")
            raise
    
    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save_config()
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "max_global_tasks": self.config.max_global_tasks,
            "max_tasks_per_user": self.config.max_tasks_per_user,
            "max_fetch_concurrent": self.config.max_fetch_concurrent,
            "max_upload_concurrent": self.config.max_upload_concurrent,
            "max_solve_concurrent": self.config.max_solve_concurrent,
            "max_llm_concurrent": self.config.max_llm_concurrent,
            "max_llm_per_provider": self.config.max_llm_per_provider,
            "max_compile_concurrent": self.config.max_compile_concurrent,
            "max_queue_size": self.config.max_queue_size,
            "task_timeout_seconds": self.config.task_timeout_seconds,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取所有统计信息"""
        stats = {}
        for name, sem in self._semaphores.items():
            s = sem.get_stats()
            stats[name] = {
                "max": s.max_count,
                "current": s.current_count,
                "waiting": s.waiting_count,
                "total_acquired": s.total_acquired,
            }
        return stats
    
    # ========== 获取信号量 ==========
    
    def acquire_global_task(self, timeout: Optional[float] = None) -> bool:
        """获取全局任务许可"""
        return self._semaphores["global_tasks"].acquire(timeout=timeout)
    
    def release_global_task(self):
        """释放全局任务许可"""
        self._semaphores["global_tasks"].release()
    
    def acquire_user_task(self, user_id: int, timeout: Optional[float] = None) -> bool:
        """获取用户任务许可"""
        if user_id not in self._user_semaphores:
            self._user_semaphores[user_id] = ManagedSemaphore(
                f"用户{user_id}", 
                self.config.max_tasks_per_user
            )
        return self._user_semaphores[user_id].acquire(timeout=timeout)
    
    def release_user_task(self, user_id: int):
        """释放用户任务许可"""
        if user_id in self._user_semaphores:
            self._user_semaphores[user_id].release()
    
    def acquire_adapter_function(self, function: str, timeout: Optional[float] = None) -> bool:
        """获取适配器功能许可 (fetch/upload/solve)"""
        if function not in self._semaphores:
            return True  # 未定义的功能不限制
        return self._semaphores[function].acquire(timeout=timeout)
    
    def release_adapter_function(self, function: str):
        """释放适配器功能许可"""
        if function in self._semaphores:
            self._semaphores[function].release()
    
    def acquire_llm(self, timeout: Optional[float] = None) -> bool:
        """获取LLM许可"""
        return self._semaphores["llm"].acquire(timeout=timeout)
    
    def release_llm(self):
        """释放LLM许可"""
        self._semaphores["llm"].release()
    
    def acquire_compile(self, timeout: Optional[float] = None) -> bool:
        """获取本地编译验题许可"""
        return self._semaphores["compile"].acquire(timeout=timeout)
    
    def release_compile(self):
        """释放本地编译验题许可"""
        self._semaphores["compile"].release()
    
    # ========== 上下文管理器 ==========
    
    @contextmanager
    def task_context(self, user_id: int, timeout: float = 30.0):
        """任务执行上下文"""
        if not self.acquire_global_task(timeout=timeout):
            raise TimeoutError("全局任务队列已满")
        
        try:
            if not self.acquire_user_task(user_id, timeout=timeout):
                self.release_global_task()
                raise TimeoutError(f"用户 {user_id} 任务队列已满")
            
            try:
                yield
            finally:
                self.release_user_task(user_id)
        finally:
            self.release_global_task()
    
    @contextmanager
    def fetch_context(self, timeout: float = 30.0):
        """拉取操作上下文"""
        if not self.acquire_adapter_function("fetch", timeout=timeout):
            raise TimeoutError("拉取队列已满")
        try:
            yield
        finally:
            self.release_adapter_function("fetch")
    
    @contextmanager
    def upload_context(self, timeout: float = 30.0):
        """上传操作上下文"""
        if not self.acquire_adapter_function("upload", timeout=timeout):
            raise TimeoutError("上传队列已满")
        try:
            yield
        finally:
            self.release_adapter_function("upload")
    
    @contextmanager
    def solve_context(self, timeout: float = 30.0):
        """求解操作上下文"""
        if not self.acquire_adapter_function("solve", timeout=timeout):
            raise TimeoutError("求解队列已满")
        try:
            yield
        finally:
            self.release_adapter_function("solve")
    
    @contextmanager
    def llm_context(self, timeout: float = 60.0):
        """LLM操作上下文"""
        if not self.acquire_llm(timeout=timeout):
            raise TimeoutError("LLM队列已满")
        try:
            yield
        finally:
            self.release_llm()
    
    @contextmanager
    def compile_context(self, timeout: float = 120.0):
        """本地编译验题操作上下文"""
        if not self.acquire_compile(timeout=timeout):
            raise TimeoutError("编译队列已满")
        try:
            yield
        finally:
            self.release_compile()


def get_concurrency_manager() -> ConcurrencyManager:
    """获取并发管理器单例"""
    return ConcurrencyManager()
