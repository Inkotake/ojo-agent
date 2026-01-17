"""
WebSocket实时通信
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set
from loguru import logger
import json
import asyncio

from core.events import get_event_bus, EventType, Event

router = APIRouter()


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._event_bus = get_event_bus()
        self._subscribed = False
    
    async def connect(self, websocket: WebSocket):
        """连接WebSocket"""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # 首次连接时订阅事件
        if not self._subscribed:
            self._subscribe_events()
            self._subscribed = True
        
        logger.info(f"WebSocket连接: {websocket.client}, 当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket断开: {websocket.client}, 当前连接数: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        if not self.active_connections:
            return
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 移除断开的连接
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.warning(f"发送消息失败: {e}")
                disconnected.add(connection)
        
        # 清理断开的连接
        self.active_connections -= disconnected
    
    def _subscribe_events(self):
        """订阅事件总线"""
        def on_event(event: Event):
            """事件处理器（同步）"""
            try:
                # 将事件转换为WebSocket消息
                message = {
                    "type": event.type.value if hasattr(event.type, 'value') else str(event.type),
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data
                }
                
                # 创建异步任务广播消息
                asyncio.create_task(self.broadcast(message))
            except Exception as e:
                logger.error(f"事件处理失败: {e}")
        
        # 订阅所有事件
        self._event_bus.subscribe("*", on_event)
        logger.info("WebSocket已订阅事件总线")


# 全局连接管理器
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket端点
    提供实时任务进度推送
    """
    await manager.connect(websocket)
    
    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "welcome",
            "message": "已连接到OJO WebSocket服务器",
            "version": "9.0.0"
        })
        
        # 保持连接
        while True:
            # 接收客户端消息（心跳等）
            data = await websocket.receive_text()
            
            # 处理心跳
            if data == "ping":
                await websocket.send_text("pong")
            else:
                # 其他消息暂不处理
                logger.debug(f"收到WebSocket消息: {data}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket正常断开")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        manager.disconnect(websocket)

