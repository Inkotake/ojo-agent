# -*- coding: utf-8 -*-
# 上传服务（纯粹调用适配器，不包含任何 OJ 特定逻辑）

from __future__ import annotations
from typing import Dict, Any

from loguru import logger
from utils.concurrency import acquire, SemaphorePool
from services.oj_api import OJAuth


class UploadService:
    """上传服务（纯粹调用适配器，不包含任何 OJ 特定逻辑）
    
    所有 OJ 特定的上传和更新逻辑都在适配器内部实现。
    本服务只负责调用适配器的统一接口。
    """
    
    def __init__(self, upload_adapter, sems: SemaphorePool | None = None, log_callback=None):
        """初始化上传服务
        
        Args:
            upload_adapter: OJ 上传适配器（必需）
            sems: 信号量池（可选）
            log_callback: 日志回调函数（可选）
        """
        if not upload_adapter:
            raise ValueError("upload_adapter 是必需的参数")
        
        self.upload_adapter = upload_adapter
        self.sems = sems
        self.log_callback = log_callback or (lambda msg: None)

    def _log(self, pid: str, msg: str):
        """记录日志"""
        self.log_callback(f"[{pid}] {msg}")

    def upload_and_update(self, auth: OJAuth, original_id: str, zip_path: str, skip_update: bool = False) -> Dict[str, Any]:
        """上传测试数据并更新题目配置（统一接口）
        
        所有 OJ 特定逻辑都在适配器内部，程序只负责调用适配器。
        
        Args:
            auth: 认证对象
            original_id: 原始题目ID或URL
            zip_path: 测试数据zip文件路径
            skip_update: 如果为True，跳过更新已存在题目，直接创建新题目（仅对支持此功能的OJ有效）
            
        Returns:
            上传结果字典
        """
        # 调用适配器的完整方法（所有 OJ 特定逻辑都在适配器内部）
        if self.sems:
            with acquire(self.sems.oj_write):
                return self.upload_adapter.upload_and_update_problem(
                    auth, original_id, zip_path, log_callback=self._log, skip_update=skip_update
                )
        else:
            return self.upload_adapter.upload_and_update_problem(
                auth, original_id, zip_path, log_callback=self._log, skip_update=skip_update
            )
