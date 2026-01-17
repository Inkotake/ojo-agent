# -*- coding: utf-8 -*-
"""全局限流协调器 - 避免多题并行时各自被OJ拒绝"""

from __future__ import annotations
import threading
import time
from typing import Optional


class RateLimitGate:
    """全局限流协调器（进程内单例）
    
    当任一线程检测到"提交频率过快"时，设置全局冷却截止时间。
    其他线程在提交前检查gate，若仍在冷却期则本地等待。
    
    ⚠ Potential behavior change: 会改变日志时间点和总体时间分配
    """
    
    _instance: Optional['RateLimitGate'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, enabled: bool = False):
        # 只初始化一次
        if not hasattr(self, '_initialized'):
            self.enabled = enabled
            self.cooldown_until = 0.0  # 冷却截止时间戳
            self.gate_lock = threading.Lock()
            self.hit_count = 0  # 统计命中次数（用于监控）
            self._initialized = True
    
    def set_cooldown(self, duration_s: int = 60):
        """设置全局冷却（当检测到限流错误时调用）"""
        if not self.enabled:
            return  # 未启用时不做任何事
        
        with self.gate_lock:
            new_until = time.time() + duration_s
            if new_until > self.cooldown_until:
                self.cooldown_until = new_until
                self.hit_count += 1
    
    def check_and_wait(self, pid: str = "", log_callback=None):
        """检查gate并等待（在提交前调用）"""
        if not self.enabled:
            return  # 未启用时不做任何事
        
        with self.gate_lock:
            remaining = self.cooldown_until - time.time()
        
        if remaining > 0:
            if log_callback:
                log_callback(f"[{pid}] ⚙ 全局限流gate生效，等待{remaining:.1f}秒...")
            time.sleep(remaining)
    
    def get_stats(self) -> dict:
        """获取统计信息（用于监控）"""
        with self.gate_lock:
            return {
                "enabled": self.enabled,
                "hit_count": self.hit_count,
                "cooldown_until": self.cooldown_until,
                "is_cooling": time.time() < self.cooldown_until
            }
    
    def reset_stats(self):
        """重置统计"""
        with self.gate_lock:
            self.hit_count = 0

