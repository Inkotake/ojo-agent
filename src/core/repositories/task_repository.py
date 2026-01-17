# -*- coding: utf-8 -*-
"""
任务数据仓库
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger


class TaskRepository:
    """任务数据访问层"""
    
    def __init__(self, db=None):
        self._db = db
    
    @property
    def db(self):
        if self._db is None:
            from core.database import get_database
            self._db = get_database()
        return self._db
    
    def find_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 查找任务"""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def find_by_user(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户的任务列表"""
        return self.db.get_user_tasks(user_id, limit=limit)
    
    def find_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取所有任务"""
        return self.db.get_all_tasks(limit=limit)
    
    def create(self, user_id: int, problem_id: str, source_oj: str = None,
               target_oj: str = None) -> int:
        """创建任务，返回任务 ID"""
        return self.db.create_task(
            user_id=user_id,
            problem_id=problem_id,
            source_oj=source_oj,
            target_oj=target_oj
        )
    
    def update(self, task_id: int, **kwargs) -> bool:
        """更新任务"""
        self.db.update_task(task_id, **kwargs)
        return True
    
    def update_status(self, task_id: int, status: int, stage: str = None,
                      progress: int = None, error_message: str = None,
                      uploaded_url: str = None) -> bool:
        """更新任务状态"""
        update_kwargs = {"status": status}
        if stage is not None:
            update_kwargs["stage"] = stage
        if progress is not None:
            update_kwargs["progress"] = progress
        if error_message is not None:
            update_kwargs["error_message"] = error_message
        if uploaded_url is not None:
            update_kwargs["uploaded_url"] = uploaded_url
        
        self.db.update_task(task_id, **update_kwargs)
        return True
    
    def delete(self, task_id: int) -> bool:
        """删除任务"""
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.db.conn.commit()
        return cursor.rowcount > 0
    
    def delete_by_user(self, user_id: int) -> int:
        """删除用户的所有任务，返回删除数量"""
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        self.db.conn.commit()
        return cursor.rowcount
    
    def count_by_status(self, user_id: int = None) -> Dict[str, int]:
        """统计各状态任务数量"""
        if user_id:
            tasks = self.find_by_user(user_id, limit=10000)
        else:
            tasks = self.find_all(limit=10000)
        
        return {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.get("status") == 0),
            "running": sum(1 for t in tasks if t.get("status") in [1, 2]),
            "success": sum(1 for t in tasks if t.get("status") == 4),
            "failed": sum(1 for t in tasks if t.get("status") == -1),
        }


# 单例
_task_repo: Optional[TaskRepository] = None


def get_task_repository() -> TaskRepository:
    """获取任务仓库实例"""
    global _task_repo
    if _task_repo is None:
        _task_repo = TaskRepository()
    return _task_repo
