# -*- coding: utf-8 -*-
"""
WebSocket 连接管理器 v9.0

统一管理所有 WebSocket 连接，支持广播和单播。
"""

from typing import List, Dict, Optional
from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """WebSocket 连接管理器（单例）"""
    
    _instance: Optional['ConnectionManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.active_connections: List[WebSocket] = []
            cls._instance.user_connections: Dict[int, List[WebSocket]] = {}
        return cls._instance
    
    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None):
        """接受连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)
        
        logger.info(f"WebSocket连接: 当前{len(self.active_connections)}个活跃连接")
    
    def disconnect(self, websocket: WebSocket, user_id: Optional[int] = None):
        """断开连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if user_id and user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
        
        logger.info(f"WebSocket断开: 当前{len(self.active_connections)}个活跃连接")
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.debug(f"WebSocket发送失败: {e}")
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
    
    async def send_to_user(self, user_id: int, message: dict):
        """发送消息给特定用户"""
        if user_id not in self.user_connections:
            return
        
        disconnected = []
        for connection in self.user_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            if conn in self.user_connections[user_id]:
                self.user_connections[user_id].remove(conn)


# 全局实例
_manager: Optional[ConnectionManager] = None


def get_ws_manager() -> ConnectionManager:
    """获取 WebSocket 管理器实例"""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
