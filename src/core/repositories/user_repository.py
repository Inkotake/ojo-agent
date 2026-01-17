# -*- coding: utf-8 -*-
"""
用户数据仓库
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger


class UserRepository:
    """用户数据访问层"""
    
    def __init__(self, db=None):
        self._db = db
    
    @property
    def db(self):
        if self._db is None:
            from core.database import get_database
            self._db = get_database()
        return self._db
    
    def find_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 查找用户"""
        return self.db.get_user_by_id(user_id)
    
    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名查找用户"""
        return self.db.get_user_by_username(username)
    
    def find_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取所有用户"""
        return self.db.get_all_users()[:limit]
    
    def create(self, username: str, password_hash: str, role: str = "user", 
               email: str = "") -> int:
        """创建用户，返回用户 ID"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, role, email, status, created_at)
            VALUES (?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
        """, (username, password_hash, role, email))
        self.db.conn.commit()
        return cursor.lastrowid
    
    def update_password(self, user_id: int, password_hash: str) -> bool:
        """更新密码"""
        cursor = self.db.conn.cursor()
        cursor.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (password_hash, user_id)
        )
        self.db.conn.commit()
        return cursor.rowcount > 0
    
    def update_role(self, user_id: int, role: str) -> bool:
        """更新角色"""
        cursor = self.db.conn.cursor()
        cursor.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (role, user_id)
        )
        self.db.conn.commit()
        return cursor.rowcount > 0
    
    def update_status(self, user_id: int, status: str) -> bool:
        """更新状态"""
        cursor = self.db.conn.cursor()
        cursor.execute(
            "UPDATE users SET status = ? WHERE id = ?",
            (status, user_id)
        )
        self.db.conn.commit()
        return cursor.rowcount > 0
    
    def update_last_login(self, user_id: int) -> bool:
        """更新最后登录时间"""
        return self.db.update_last_login(user_id)
    
    def delete(self, user_id: int) -> bool:
        """删除用户"""
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.db.conn.commit()
        return cursor.rowcount > 0
    
    def exists(self, username: str) -> bool:
        """检查用户名是否存在"""
        return self.find_by_username(username) is not None


# 单例
_user_repo: Optional[UserRepository] = None


def get_user_repository() -> UserRepository:
    """获取用户仓库实例"""
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepository()
    return _user_repo
