# -*- coding: utf-8 -*-
"""LLM流式输出处理器 - 统一管理流式传输和日志"""

from __future__ import annotations
import threading
from pathlib import Path
from typing import Callable, Optional
from loguru import logger


class StreamHandler:
    """LLM流式输出处理器（通用）
    
    职责：
    - 管理reasoning和content缓冲区
    - 定期输出到日志文件（避免过于频繁）
    - 处理流式块的累积和限制
    - 实时推送日志到回调（用于WebSocket）
    """
    
    def __init__(self, log_file: Path, buffer_limit: int = 200, log_callback: Optional[Callable[[str], None]] = None):
        """
        Args:
            log_file: 日志文件路径（如problem.log）
            buffer_limit: 缓冲区输出阈值（字符数）
            log_callback: 日志回调函数（用于实时推送）
        """
        self.log_file = log_file
        self.buffer_limit = buffer_limit
        self.log_callback = log_callback
        self.reasoning_buffer = []
        self.content_buffer = []
        self.buffer_lock = threading.Lock()
        self._last_callback_time = 0
        self._callback_interval = 0.5  # 回调间隔（秒），避免过于频繁
    
    def on_chunk(self, reasoning_chunk: str, content_chunk: str, pid: str = ""):
        """处理流式块（写入日志文件并实时推送）
        
        Args:
            reasoning_chunk: 思考过程块
            content_chunk: 内容块
            pid: 题目ID（用于调试）
        """
        import time
        
        if not reasoning_chunk and not content_chunk:
            return
        
        try:
            with self.buffer_lock:
                lines_to_callback = []  # 收集要回调的日志行
                
                # 处理reasoning
                if reasoning_chunk:
                    self.reasoning_buffer.append(reasoning_chunk)
                    current_content = ''.join(self.reasoning_buffer)
                    
                    # 遇到换行符或达到上限时写入
                    if '\n' in reasoning_chunk or len(current_content) >= self.buffer_limit:
                        try:
                            with open(self.log_file, "a", encoding="utf-8", errors="ignore") as f:
                                if '\n' in reasoning_chunk:
                                    lines = current_content.split('\n')
                                    for line in lines[:-1]:
                                        if line.strip():
                                            log_line = f"[思考] {line}"
                                            f.write(log_line + "\n")
                                            lines_to_callback.append(log_line)
                                    self.reasoning_buffer.clear()
                                    if lines[-1]:
                                        self.reasoning_buffer.append(lines[-1])
                                else:
                                    log_line = f"[思考] {current_content}"
                                    f.write(log_line + "\n")
                                    lines_to_callback.append(log_line)
                                    self.reasoning_buffer.clear()
                        except Exception:
                            pass
                
                # 处理content
                if content_chunk:
                    self.content_buffer.append(content_chunk)
                    current_code = ''.join(self.content_buffer)
                    
                    # 遇到换行符或达到上限时写入
                    if '\n' in content_chunk or len(current_code) >= self.buffer_limit:
                        try:
                            with open(self.log_file, "a", encoding="utf-8", errors="ignore") as f:
                                if '\n' in content_chunk:
                                    lines = current_code.split('\n')
                                    for line in lines[:-1]:
                                        if line.strip():
                                            log_line = f"[代码] {line}"
                                            f.write(log_line + "\n")
                                            lines_to_callback.append(log_line)
                                    self.content_buffer.clear()
                                    if lines[-1]:
                                        self.content_buffer.append(lines[-1])
                                else:
                                    log_line = f"[代码] {current_code}"
                                    f.write(log_line + "\n")
                                    lines_to_callback.append(log_line)
                                    self.content_buffer.clear()
                        except Exception:
                            pass
                
                # 实时回调推送（节流控制）
                if self.log_callback and lines_to_callback:
                    now = time.time()
                    if now - self._last_callback_time >= self._callback_interval:
                        self._last_callback_time = now
                        for line in lines_to_callback:
                            try:
                                self.log_callback(f"[{pid}] {line}")
                            except Exception:
                                pass
                                
        except Exception as e:
            logger.debug(f"[{pid}] StreamHandler on_chunk error: {e}")
    
    def get_accumulated(self) -> tuple[str, str]:
        """获取累积的内容（不清空）"""
        with self.buffer_lock:
            reasoning = ''.join(self.reasoning_buffer)
            content = ''.join(self.content_buffer)
            return reasoning, content
    
    def reset(self):
        """重置缓冲区"""
        with self.buffer_lock:
            self.reasoning_buffer = []
            self.content_buffer = []

    def flush(self, pid: str = "") -> None:
        """将缓冲区残留内容写入日志并推送回调"""
        try:
            with self.buffer_lock:
                if not self.reasoning_buffer and not self.content_buffer:
                    return
                
                lines_to_callback = []
                
                try:
                    with open(self.log_file, "a", encoding="utf-8", errors="ignore") as f:
                        if self.reasoning_buffer:
                            remaining_reasoning = ''.join(self.reasoning_buffer)
                            for line in remaining_reasoning.split('\n'):
                                if line.strip():
                                    log_line = f"[思考] {line}"
                                    f.write(log_line + "\n")
                                    lines_to_callback.append(log_line)
                            self.reasoning_buffer.clear()
                        if self.content_buffer:
                            remaining_content = ''.join(self.content_buffer)
                            for line in remaining_content.split('\n'):
                                if line.strip():
                                    log_line = f"[代码] {line}"
                                    f.write(log_line + "\n")
                                    lines_to_callback.append(log_line)
                            self.content_buffer.clear()
                except Exception:
                    pass
                
                # 推送残留内容到回调
                if self.log_callback and lines_to_callback:
                    for line in lines_to_callback:
                        try:
                            self.log_callback(f"[{pid}] {line}" if pid else line)
                        except Exception:
                            pass
                            
        except Exception as e:
            logger.debug(f"[{self.log_file}] StreamHandler flush error: {e}")

