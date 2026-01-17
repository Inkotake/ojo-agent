# -*- coding: utf-8 -*-
# 团队题单：封装登录/创建/查找/批量加题  fileciteturn0file3

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any

from loguru import logger

from services.oj_api import OJApi, OJAuth


@dataclass
class TrainingContext:
    tid: Optional[int]
    title: str
    description: str


class TrainingService:
    def __init__(self, oj: OJApi):
        self.oj = oj
    
    def _coerce_pid_value(self, pid: str) -> int | str:
        """PID类型强制转换（内部辅助）"""
        return int(pid) if str(pid).isdigit() else pid

    def create_or_find_training(self, auth: OJAuth, gid: int, rank: int, category_id: Optional[int],
                                auth_mode: str, private_pwd: str, status: bool,
                                title: str, description: str, author: str) -> TrainingContext:
        # 使用配置中指定的名称和描述，不添加前缀后缀
        url = f"{self.oj.api_base_url}/api/group/training"
        headers = {"authorization": auth.token, "Content-Type": "application/json;charset=UTF-8"}
        payload = {
            "training": {
                "rank": rank, "title": title, "description": description, "privatePwd": private_pwd,
                "auth": auth_mode, "status": status, "gid": gid, "author": author
            },
            "trainingCategory": {"id": category_id},
        }
        r = auth.session.post(url, headers=headers, json=payload, timeout=self.oj.timeout)
        r.raise_for_status()
        data = r.json()
        if data.get("code") not in (0, 200):
            raise RuntimeError(f"创建训练失败: {data}")

        # 再查询列表找到 tid（最新同名最大 id）
        url_list = f"{self.oj.api_base_url}/api/group/get-admin-training-list"
        params = {"currentPage": 1, "limit": 50, "gid": gid}
        tid = None
        r2 = auth.session.get(url_list, headers={"authorization": auth.token}, params=params, timeout=self.oj.timeout)
        r2.raise_for_status()
        for rec in (r2.json().get("data", {}).get("records") or []):
            if rec.get("title") == title:
                if tid is None or int(rec["id"]) > int(tid):
                    tid = int(rec["id"])
        if tid is None:
            raise RuntimeError("无法定位新建训练的 ID")
        return TrainingContext(tid=tid, title=title, description=description)

    def add_problems(self, auth: OJAuth, tid: int, problems: List[str]) -> Dict[str, Any]:
        """添加题目到题单，返回详细结果"""
        url = f"{self.oj.api_base_url}/api/group/add-training-problem-from-public"
        headers = {"authorization": auth.token, "Content-Type": "application/json;charset=UTF-8"}
        
        results = {
            'success': [],
            'failed': [],
            'total': len(problems)
        }
        
        for original_pid in problems:
            try:
                # 先解析获取后端ID
                try:
                    actual_id, display_id = self.oj.resolve_actual_id(auth, original_pid)
                    logger.debug(f"题目 {original_pid} 解析为: actual_id={actual_id}, display_id={display_id}")
                except Exception as resolve_err:
                    logger.warning(f"题目 {original_pid} 解析失败: {resolve_err}，使用原始ID")
                    # 解析失败时使用原始ID
                    actual_id = self._coerce_pid_value(original_pid)
                    display_id = str(original_pid)
                
                payload = {
                    "pid": actual_id,           # 后端ID（int）
                    "tid": tid,
                    "displayId": display_id      # 显示ID（字符串，原始输入）
                }
                
                r = auth.session.post(url, headers=headers, json=payload, timeout=self.oj.timeout)
                r.raise_for_status()
                data = r.json()
                
                if data.get("code") in (0, 200):
                    results['success'].append(original_pid)
                else:
                    error_msg = data.get('msg') or data.get('message') or '未知错误'
                    results['failed'].append({
                        'pid': original_pid,
                        'reason': error_msg
                    })
                    logger.error(f"加题失败 {original_pid}: {error_msg}")
            except Exception as e:
                results['failed'].append({
                    'pid': original_pid,
                    'reason': str(e)
                })
                logger.error(f"加题异常 {original_pid}: {e}")
        
        return results
