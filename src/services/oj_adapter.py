# -*- coding: utf-8 -*-
"""OJ适配器 - 使用模块化的SHSOJ实现

此适配器使用细分的SHSOJ模块，保持：
- 相同的参数和返回值
- 相同的请求顺序和时序
- 相同的异常和错误处理
- 相同的超时/代理/证书校验
"""

from __future__ import annotations
from typing import Any, Dict, List
from .oj_api import OJApi, OJAuth
from loguru import logger


class OJApiAdapter:
    """OJ适配器（使用模块化SHSOJ或直通旧OJApi）"""
    
    def __init__(self, api: OJApi):
        # 兼容模式：直接使用传入的OJApi
        # 未来可以检测api类型并使用不同的Adapter
        self._api = api
    
    def _normalize_problem_id_for_api(self, original_id: str) -> str:
        """将 URL/混合形式的问题标识转换为后端API需要的实际 problemId（通常是纯数字）"""
        try:
            # 仅当明显是URL或包含非数字字符时尝试解析
            if isinstance(original_id, str) and (original_id.startswith("http://") or original_id.startswith("https://") or not original_id.isdigit()):
                from services.oj.registry import get_global_registry
                registry = get_global_registry()
                if registry:
                    adapter = registry.find_adapter_by_url(original_id)
                    if adapter:
                        fetcher = adapter.get_problem_fetcher()
                        if fetcher:
                            parsed = fetcher.parse_problem_id(original_id)
                            if parsed:
                                logger.debug(f"OJApiAdapter: 将原始ID {original_id} 规范化为后端ID {parsed}")
                                return str(parsed)
        except Exception as e:
            logger.debug(f"OJApiAdapter: 规范化问题ID失败 ({original_id}): {e}")
        # 回退：原样返回
        return str(original_id)

    # Read operations - 对需要problemId的接口做规范化
    
    def get_problem_detail(self, original_id: str) -> Dict[str, Any]:
        """获取公开的题目详情（对URL做ID解析后再请求）"""
        normalized = self._normalize_problem_id_for_api(original_id)
        return self._api.get_problem_detail(normalized)
    
    def fetch_admin_problem(self, auth: OJAuth, pid: int) -> Dict[str, Any]:
        """获取管理员题目信息（直通）"""
        return self._api.fetch_admin_problem(auth, pid)
    
    def fetch_problem_cases(self, auth: OJAuth, pid: int) -> List[Dict[str, Any]]:
        """获取题目测试用例信息（直通）"""
        return self._api.fetch_problem_cases(auth, pid)
    
    def get_submission_detail(self, auth: OJAuth, submit_id: int) -> Dict[str, Any]:
        """获取提交详情（直通）"""
        return self._api.get_submission_detail(auth, submit_id)
    
    def resolve_actual_id(self, auth: OJAuth, original_id: str):
        """解析实际题目ID（直通）"""
        return self._api.resolve_actual_id(auth, original_id)
    
    # Write operations - 纯直通，不添加任何逻辑
    
    def upload_testcase_zip(self, auth: OJAuth, zip_path: str, mode: str = "default") -> Dict[str, Any]:
        """上传测试用例zip文件（直通）"""
        return self._api.upload_testcase_zip(auth, zip_path, mode)
    
    def put_admin_problem(self, auth: OJAuth, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新管理员题目信息（直通）"""
        return self._api.put_admin_problem(auth, payload)
    
    def submit_problem_judge(self, auth: OJAuth, original_id: str, code: str, language: str = "C++") -> int:
        """提交题目判题（对URL做ID解析后再请求）"""
        normalized = self._normalize_problem_id_for_api(original_id)
        return self._api.submit_problem_judge(auth, normalized, code, language)

