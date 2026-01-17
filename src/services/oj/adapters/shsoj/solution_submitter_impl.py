# -*- coding: utf-8 -*-
"""SHSOJ解题提交实现（适配新接口）"""

from typing import Dict, Any
import json
from loguru import logger

from ...base.solution_submitter import SolutionSubmitter
from .url_utils import derive_api_url, derive_frontend_url


class SHSOJSolutionSubmitter(SolutionSubmitter):
    """SHSOJ解题提交器（实现新接口）"""
    
    def __init__(self, base_url: str, timeout: int, proxies: dict = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxies = proxies
        self.verify_ssl = verify_ssl
        # 推导API URL（确保使用正确的API端点）
        self.api_base_url = derive_api_url(self.base_url)
    
    def submit_solution(self, problem_id: str, code: str, language: str, auth: Any) -> Dict[str, Any]:
        """提交解题代码
        
        Args:
            problem_id: 题目ID
            code: 代码内容
            language: 编程语言
            auth: SHSOJ认证对象
            
        Returns:
            提交结果（包含submit_id和status）
        """
        try:
            submit_id = self.submit_problem_judge(auth, problem_id, code, language)
            return {
                "status": "success",
                "submission_id": str(submit_id),
                "submit_id": str(submit_id),  # 兼容字段
                "problem_id": problem_id,
                "language": language
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "submission_id": None,
                "submit_id": None
            }
    
    def get_submission_status(self, submission_id: str, auth: Any) -> Dict[str, Any]:
        """查询提交状态
        
        Args:
            submission_id: 提交ID
            auth: SHSOJ认证对象
            
        Returns:
            提交状态信息（格式化为标准格式）
        """
        from ...shsoj.status_codes import get_status_name, is_accepted
        
        detail = self.get_submission_detail(auth, int(submission_id))
        
        # 获取状态码
        status_code = detail.get("status", -1)
        status_name = get_status_name(status_code)
        is_accepted_flag = is_accepted(status_code)
        
        # 返回标准格式
        result = {
            "status": status_name,
            "status_code": status_code,
            "is_accepted": is_accepted_flag,
            "score": detail.get("score"),  # SHSOJ可能没有score字段
        }
        
        # 保留原始数据
        result["raw"] = detail
        
        return result
    
    def supported_languages(self) -> list[str]:
        """SHSOJ支持的编程语言"""
        return [
            "C",
            "C++",
            "C++ With O2",
            "Java",
            "Python2",
            "Python3",
            "PyPy2",
            "PyPy3",
            "Golang",
            "JavaScript Node",
            "C#"
        ]
    
    def get_default_language(self, lang_hint: str = "C++") -> str:
        """获取默认语言键
        
        Args:
            lang_hint: 语言提示（如 "C++", "Python"）
            
        Returns:
            SHSOJ 使用的语言键
        """
        hint_lower = lang_hint.lower()
        if "c++" in hint_lower or "cpp" in hint_lower:
            return "C++ With O2"
        elif "python3" in hint_lower or "py3" in hint_lower:
            return "Python3"
        elif "python" in hint_lower or "py" in hint_lower:
            return "Python3"
        elif "java" in hint_lower:
            return "Java"
        else:
            return "C++ With O2"  # 默认 C++
    
    def submit_problem_judge(self, auth, original_id: str, code: str, language: str = "C++") -> int:
        """提交代码到OJ判题（SHSOJ原生API）"""
        # 使用与 oj_api.py 相同的格式
        url = f"{self.api_base_url}/api/submit-problem-judge"
        payload = {
            "pid": str(original_id),  # 注意：使用 "pid" 而不是 "problemId"
            "language": language,
            "code": code,
            "cid": 0,
            "tid": None,
            "gid": None,
            "isRemote": False,
        }
        
        # 使用与 oj_api.py 相同的 headers
        # 注意：Origin 和 Referer 应使用前端URL，而非API URL
        frontend_url = derive_frontend_url(self.base_url)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": frontend_url,
            "Referer": frontend_url + "/",
            "Url-Type": "general",  # 注意：大写 U
            "User-Agent": "Mozilla/5.0 (compatible; ojo_batch_tool/1.0)",
        }
        
        # 添加 authorization（如果 auth 有 token）
        if hasattr(auth, 'token') and auth.token:
            headers["authorization"] = auth.token
        
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        
        try:
            r = auth.session.post(url, data=data_bytes, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        except Exception as e:
            logger.error(f"SHSOJ提交请求异常: {e}, URL: {url}")
            raise RuntimeError(f"提交请求失败: {e}")
        
        if r.status_code != 200:
            error_text = r.text[:200] if r.text else ""
            logger.error(f"SHSOJ提交失败: HTTP {r.status_code}, URL: {url}, Response: {error_text}")
            raise RuntimeError(f"提交失败: HTTP {r.status_code} - {error_text}")
        
        try:
            obj = r.json()
        except Exception as e:
            logger.error(f"SHSOJ提交响应解析失败: {e}, Response text: {r.text[:200]}")
            raise RuntimeError(f"提交响应解析失败: {e}")
        
        code_val = obj.get("code")
        
        if code_val == 10002:
            raise RuntimeError("提交频率过快，请稍后再试")
        
        if code_val not in (0, 200):
            msg = obj.get("msg") or obj.get("message") or "未知错误"
            logger.error(f"SHSOJ提交业务错误: code={code_val}, msg={msg}")
            raise RuntimeError(f"提交失败: {msg} (code: {code_val})")
        
        # 注意：响应格式可能是 data.submitId 或直接 data
        data = obj.get("data", {})
        if isinstance(data, dict):
            submit_id = data.get("submitId")
        else:
            submit_id = data
        
        if submit_id is None:
            logger.error(f"SHSOJ提交成功但未返回提交ID: {obj}")
            raise RuntimeError(f"提交成功但未返回提交ID: {obj}")
        
        return int(submit_id)
    
    def get_submission_detail(self, auth, submit_id: int) -> Dict[str, Any]:
        """获取提交详情（SHSOJ原生API）"""
        url = f"{self.api_base_url}/api/get-submission-detail?submitId={submit_id}"
        # 注意：Origin 和 Referer 应使用前端URL，而非API URL
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (compatible; ojo_batch_tool/1.0)",
            "Url-Type": "general",  # 注意：大写 U
            "Origin": derive_frontend_url(self.base_url),
            "Referer": derive_frontend_url(self.base_url) + "/",
        }
        
        # 添加 authorization（如果 auth 有 token）
        if hasattr(auth, 'token') and auth.token:
            headers["authorization"] = auth.token
        
        r = auth.session.get(url, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        
        if r.status_code != 200:
            raise RuntimeError(f"获取提交详情失败: HTTP {r.status_code}")
        
        obj = r.json()
        if obj.get("code") not in (0, 200):
            raise RuntimeError(f"获取提交详情失败: {obj}")
        
        # 注意：响应格式可能是 data.submission 或直接 data
        data = obj.get("data", {})
        if isinstance(data, dict) and "submission" in data:
            return data.get("submission", {})
        return data

