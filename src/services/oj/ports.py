# -*- coding: utf-8 -*-
"""OJ API 抽象接口（用于多OJ支持）

细粒度Port定义，支持模块化实现。
"""

from __future__ import annotations
from typing import Protocol, Any, Dict, Tuple, List


class ProblemFetcherPort(Protocol):
    """题面获取接口"""
    
    def get_problem_detail(self, pid: str | int) -> Dict[str, Any]:
        """获取公开题目详情"""
        ...
    
    def fetch_admin_problem(self, auth, pid: str | int) -> Dict[str, Any]:
        """获取管理员题目信息"""
        ...
    
    def resolve_actual_id(self, auth, alias_pid) -> Tuple[int, str]:
        """解析实际题目ID"""
        ...


class CaseUploaderPort(Protocol):
    """测试用例上传接口"""
    
    def upload_testcase_zip(self, auth, zip_path: str, mode: str = "default") -> Dict[str, Any]:
        """上传测试用例zip文件"""
        ...
    
    def fetch_problem_cases(self, auth, pid: int) -> List[Dict[str, Any]]:
        """获取题目测试用例信息"""
        ...
    
    def put_admin_problem(self, auth, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新管理员题目配置"""
        ...


class JudgeSubmitterPort(Protocol):
    """判题提交接口"""
    
    def submit_problem_judge(self, auth, pid, code: str, language: str = "C++") -> int:
        """提交题目判题"""
        ...
    
    def get_submission_detail(self, auth, submit_id: int) -> Dict[str, Any]:
        """获取提交详情"""
        ...


class AuthPort(Protocol):
    """认证接口"""
    
    def login_user(self, username: str, password: str):
        """登录并获取认证信息"""
        ...


class OJAdapter(ProblemFetcherPort, CaseUploaderPort, JudgeSubmitterPort, AuthPort, Protocol):
    """组合适配器：包含所有OJ操作"""
    pass


# 向后兼容的别名
OJReadPort = ProblemFetcherPort
OJWritePort = CaseUploaderPort
OJPort = OJAdapter

