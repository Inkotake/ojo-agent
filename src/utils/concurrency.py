# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time
from typing import Optional, Callable

class SemaphorePool:
    """三个独立限流的信号量：DeepSeek、OJ API读、OJ API写"""
    def __init__(self, deepseek_limit: int, oj_limit: int):
        self.ds = threading.Semaphore(max(1, deepseek_limit))
        self.oj = threading.Semaphore(max(1, oj_limit))  # OJ读取操作
        self.oj_write = threading.Semaphore(1)  # OJ写入操作（上传、提交）严格限制为1

class _Acquire:
    def __init__(self, sem: threading.Semaphore):
        self.sem = sem
    def __enter__(self):
        self.sem.acquire()
        return self
    def __exit__(self, exc_type, exc, tb):
        self.sem.release()

def acquire(sem: threading.Semaphore) -> _Acquire:
    return _Acquire(sem)

class CancelToken:
    def __init__(self):
        self._flag = False
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._flag = True

    def cancelled(self) -> bool:
        with self._lock:
            return self._flag


def interruptible_sleep(
    seconds: float, 
    cancel_check: Optional[Callable[[], bool]] = None,
    interval: float = 0.5
) -> bool:
    """可中断的等待
    
    Args:
        seconds: 等待秒数
        cancel_check: 取消检查函数，返回 True 表示需要取消
        interval: 检查间隔（默认 0.5 秒）
    
    Returns:
        bool: True 表示正常完成，False 表示被取消
    """
    if cancel_check is None:
        time.sleep(seconds)
        return True
    
    elapsed = 0.0
    while elapsed < seconds:
        if cancel_check():
            return False
        sleep_time = min(interval, seconds - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time
    return True


def retry_with_backoff(
    fn: Callable, 
    *, 
    max_attempts: int = 5, 
    base_delay: float = 1.0, 
    factor: float = 2.0, 
    on_error: Optional[Callable] = None,
    cancel_check: Optional[Callable[[], bool]] = None
):
    """带退避的重试（支持取消检查）
    
    Args:
        fn: 要执行的函数
        max_attempts: 最大尝试次数
        base_delay: 基础延迟
        factor: 退避因子
        on_error: 错误回调
        cancel_check: 取消检查函数
    
    Returns:
        函数执行结果
    
    Raises:
        最后一次异常或 CancelledError
    """
    attempt = 0
    while True:
        # 检查取消
        if cancel_check and cancel_check():
            raise InterruptedError("操作被取消")
        
        try:
            return fn()
        except Exception as e:
            attempt += 1
            if on_error:
                try: 
                    on_error(e, attempt)
                except Exception: 
                    pass
            if attempt >= max_attempts:
                raise
            
            # 可中断的等待
            delay = base_delay * (factor ** (attempt - 1))
            if not interruptible_sleep(delay, cancel_check):
                raise InterruptedError("操作被取消")
