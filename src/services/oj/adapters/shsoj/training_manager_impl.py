# -*- coding: utf-8 -*-
"""SHSOJ题单管理实现（适配新接口）"""

from typing import Dict, Any, List
import json
from loguru import logger

from ...base.training_manager import TrainingManager
from .url_utils import derive_api_url


class SHSOJTrainingManager(TrainingManager):
    """SHSOJ题单管理器（实现新接口）"""
    
    def __init__(self, base_url: str, timeout: int, proxies: dict = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxies = proxies
        self.verify_ssl = verify_ssl
        # 推导API URL（确保使用正确的API端点）
        self.api_base_url = derive_api_url(self.base_url)
    
    def create_training(self, title: str, description: str, auth: Any, **kwargs) -> Dict[str, Any]:
        """创建题单
        
        Args:
            title: 题单标题
            description: 题单描述
            auth: SHSOJ认证对象
            **kwargs: group_id, rank, author, status等
            
        Returns:
            创建结果（包含training_id）
        """
        url = f"{self.api_base_url}/api/group/add-training"
        
        payload = {
            "gid": kwargs.get('group_id', 3609),
            "rank": kwargs.get('rank', 1000),
            "title": title,
            "description": description,
            "author": kwargs.get('author', ''),
            "status": kwargs.get('status', True),
        }
        
        headers = {
            "authorization": auth.token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        
        r = auth.session.post(url, headers=headers, json=payload, timeout=self.timeout)
        r.raise_for_status()
        
        data = r.json()
        if data.get("code") not in (0, 200):
            raise RuntimeError(f"创建题单失败: {data}")
        
        # 查找新创建的题单ID
        training_id = self._find_training_id(auth, title)
        
        return {
            "training_id": training_id,
            "title": title,
            "description": description
        }
    
    def add_problems(self, training_id: str, problem_ids: List[str], auth: Any) -> Dict[str, Any]:
        """添加题目到题单
        
        Args:
            training_id: 题单ID
            problem_ids: 题目ID列表
            auth: SHSOJ认证对象
            
        Returns:
            添加结果（success/failed列表）
        """
        url = f"{self.api_base_url}/api/group/add-training-problem-from-public"
        headers = {
            "authorization": auth.token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        
        results = {
            'success': [],
            'failed': [],
            'total': len(problem_ids)
        }
        
        for original_pid in problem_ids:
            try:
                # 解析获取后端ID（需要依赖problem_fetcher）
                # 这里简化处理，实际应该调用适配器的resolve_actual_id
                payload = {
                    "pid": int(original_pid),
                    "tid": int(training_id),
                    "displayId": str(original_pid)
                }
                
                r = auth.session.post(url, headers=headers, json=payload, timeout=self.timeout)
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
            except Exception as e:
                results['failed'].append({
                    'pid': original_pid,
                    'reason': str(e)
                })
        
        return results
    
    def get_training(self, training_id: str, auth: Any) -> Dict[str, Any]:
        """获取题单信息
        
        Args:
            training_id: 题单ID
            auth: SHSOJ认证对象
            
        Returns:
            题单信息
        """
        url = f"{self.api_base_url}/api/group/get-training?tid={training_id}"
        headers = {"authorization": auth.token}
        
        r = auth.session.get(url, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        
        data = r.json()
        if data.get("code") not in (0, 200):
            raise RuntimeError(f"获取题单失败: {data}")
        
        return data.get("data", {})
    
    def _find_training_id(self, auth, title: str) -> int:
        """查找新创建的题单ID"""
        url = f"{self.api_base_url}/api/group/get-training-list"
        payload = {"currentPage": 1, "limit": 50}
        headers = {
            "authorization": auth.token,
            "Content-Type": "application/json;charset=UTF-8"
        }
        
        r = auth.session.post(url, headers=headers, json=payload, timeout=self.timeout)
        r.raise_for_status()
        
        data = r.json()
        if data.get("code") in (0, 200):
            records = data.get("data", {}).get("records", [])
            for rec in records:
                if rec.get("title") == title:
                    return int(rec["id"])
        
        raise RuntimeError("无法定位新建题单的ID")

