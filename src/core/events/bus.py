"""
事件总线实现
"""

import asyncio
import inspect
from typing import Dict, List, Set
from collections import defaultdict
from loguru import logger

from .types import Event, EventType, EventHandler


class EventBus:
    """
    异步事件总线
    支持同步和异步事件处理器
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: List[EventHandler] = []
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task = None
    
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型（或"*"表示所有事件）
            handler: 事件处理器（可以是同步或异步函数）
        """
        event_key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        
        if event_key == "*":
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_key].append(handler)
        
        logger.debug(f"订阅事件: {event_key}, 处理器: {handler.__name__}")
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅"""
        event_key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        
        if event_key == "*":
            if handler in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(handler)
        else:
            if handler in self._subscribers[event_key]:
                self._subscribers[event_key].remove(handler)
    
    async def publish(self, event: Event) -> None:
        """
        发布事件（异步）
        
        Args:
            event: 事件对象
        """
        event_key = event.type.value if isinstance(event.type, EventType) else str(event.type)
        
        # 获取订阅者
        handlers = self._subscribers.get(event_key, []) + self._wildcard_subscribers
        
        if not handlers:
            logger.debug(f"无订阅者: {event_key}")
            return
        
        # 执行处理器
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"事件处理器执行失败: {handler.__name__}, 错误: {e}")
    
    def publish_sync(self, event: Event) -> None:
        """
        发布事件（同步，用于非异步上下文）
        实际上是将事件放入队列，由后台worker处理
        """
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果在运行中的事件循环，创建任务
                asyncio.create_task(self.publish(event))
            else:
                # 否则直接运行
                loop.run_until_complete(self.publish(event))
        except RuntimeError:
            # 没有事件循环，创建新的
            asyncio.run(self.publish(event))
    
    async def start(self) -> None:
        """启动事件总线（如果需要后台处理队列）"""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("事件总线已启动")
    
    async def stop(self) -> None:
        """停止事件总线"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("事件总线已停止")
    
    async def _process_queue(self) -> None:
        """后台worker，处理队列中的事件"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(), 
                    timeout=1.0
                )
                await self.publish(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"事件队列处理失败: {e}")
    
    def get_subscriber_count(self, event_type: EventType = None) -> int:
        """获取订阅者数量"""
        if event_type is None:
            # 返回所有订阅者总数
            return sum(len(handlers) for handlers in self._subscribers.values()) + \
                   len(self._wildcard_subscribers)
        
        event_key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        return len(self._subscribers.get(event_key, []))


# 全局事件总线实例
_global_event_bus: EventBus = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus

