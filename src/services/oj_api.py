# -*- coding: utf-8 -*-
# OJ API封装 - 完全按照原始脚本的请求格式

from __future__ import annotations

import json
import time
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List

import requests
from loguru import logger

from utils.concurrency import retry_with_backoff


@dataclass
class OJAuth:
    token: str
    session: requests.Session


class OJApi:
    """与 OJ 的交互封装 - 所有API调用完全按照原始脚本格式"""
    def __init__(self, base_url: str, timeout: int = 30, proxies: dict | None = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxies = proxies or None
        self.verify_ssl = verify_ssl
        # 推导API URL（前端URL → API URL）
        self.api_base_url = self._derive_api_url(self.base_url)
    
    def _derive_api_url(self, frontend_url: str) -> str:
        """根据前端URL自动推导API URL（与problem_fetcher_impl保持一致）"""
        url_lower = frontend_url.lower()
        
        # 如果已经是API地址，直接返回
        if 'api-tcoj.aicoders.cn' in url_lower:
            return "https://api-tcoj.aicoders.cn"
        if 'oj-api.shsbnu.net' in url_lower:
            return "https://oj-api.shsbnu.net"
        
        # 新的 aicoders.cn 平台（前端）
        if 'oj.aicoders.cn' in url_lower or 'aicoders.cn/problem' in url_lower:
            logger.debug(f"OJApi: 前端URL（aicoders） {frontend_url} → API URL https://api-tcoj.aicoders.cn")
            return "https://api-tcoj.aicoders.cn"
        
        # 旧的 shsbnu.net 平台（前端）
        if 'oj.shsbnu.net' in url_lower or 'shsbnu.net' in url_lower:
            logger.debug(f"OJApi: 前端URL（shsbnu） {frontend_url} → API URL https://oj-api.shsbnu.net")
            return "https://oj-api.shsbnu.net"
        
        # 默认使用原URL
        logger.warning(f"OJApi: 无法推导API URL，使用原URL {frontend_url}")
        return frontend_url

    def login_user(self, username: str, password: str) -> OJAuth:
        """登录并获取token（对应team.py的login_user）"""
        # 优先尝试用户配置的 base_url（多为 https://oj.shsbnu.net），失败时退回 API 域名
        login_urls = []
        frontend_login = f"{self.base_url.rstrip('/')}/api/login"
        api_login = f"{self.api_base_url.rstrip('/')}/api/login"
        login_urls.append(frontend_login)
        if api_login != frontend_login:
            login_urls.append(api_login)
        
        s = requests.Session()
        s.proxies = self.proxies or {}

        payload = {"username": username, "password": password}

        def _attempt(url: str) -> str:
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
                "Origin": self.base_url.replace("-api", ""),
                "Referer": self.base_url.replace("-api", "") + "/",
                "Url-Type": "general",
                "User-Agent": "Mozilla/5.0 (compatible; ojo_batch_tool/1.0)",
            }
            logger.debug(f"OJApi: 尝试登录 {url}")
            resp = s.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                proxies=self.proxies,
                verify=self.verify_ssl,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"登录失败，HTTP状态 {resp.status_code}: {resp.text}")
            
            token = resp.headers.get("Authorization")
            if not token:
                try:
                    data = resp.json()
                    token = data.get("data", {}).get("token") or data.get("token")
                except Exception:
                    token = None
            
            if not token:
                raise RuntimeError("登录成功但未返回Authorization token")
            
            s.headers.update({"authorization": token, "Url-Type": "general"})
            logger.debug("OJApi: 登录成功，获得token")
            return token

        def _req():
            last_exc = None
            for url in login_urls:
                try:
                    return _attempt(url)
                except Exception as exc:
                    last_exc = exc
                    logger.warning(f"OJApi: 登录地址 {url} 失败: {exc}")
            assert last_exc is not None
            raise last_exc

        token = retry_with_backoff(_req, on_error=lambda e, a: logger.warning(f"登录重试 {a}: {e}"))
        return OJAuth(token=token, session=s)

    def resolve_actual_id(self, auth: OJAuth, original_id: str) -> Tuple[int, str]:
        """解析后端的内部问题ID（对应upload.py的resolve_problem_id）"""
        url = f"{self.api_base_url}/api/admin/problem/get-admin-problem-list"
        payload = {
            "problemId": str(original_id),
            "tagIdList": [],
            "limit": 10,
            "currentPage": 1,
            "isGroup": False,
        }
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
        }
        
        try:
            r = auth.session.post(url, data=data_bytes, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
            if r.status_code == 200:
                obj = r.json()
                records = obj.get("data", {}).get("records", []) or []
                if records:
                    # 精确匹配problemId字段
                    for rec in records:
                        if rec.get("problemId") == str(original_id):
                            actual_id = rec.get("id", int(original_id))
                            problem_id_str = rec.get("problemId", str(original_id))
                            logger.debug(f"精确匹配到题目: id={actual_id}, problemId={problem_id_str}")
                            return int(actual_id), str(problem_id_str)
                    
                    # 没有精确匹配，记录警告并使用原始ID
                    logger.warning(f"未找到精确匹配的题目 {original_id}，API返回了 {len(records)} 条记录")
                    logger.warning(f"返回的记录: {[rec.get('problemId') for rec in records]}")
        except Exception as e:
            logger.debug(f"resolve_actual_id失败: {e}")
        
        return int(original_id), str(original_id)

    def get_problem_detail(self, original_id: str) -> Dict[str, Any]:
        """获取公开的题目详情（对应getdata.py的fetch_problem_detail）"""
        # 使用推导的API URL，修复双斜杠问题
        url = f"{self.api_base_url}/api/get-problem-detail?problemId={original_id}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (compatible; ojo_batch_tool/1.0)",
            "url-type": "general",
        }
        
        logger.info(f"OJApi: 请求题目详情 {original_id}")
        logger.info(f"OJApi: 使用 API URL: {url}")
        
        r = requests.get(url, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        
        logger.info(f"OJApi: HTTP {r.status_code}, Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        logger.info(f"OJApi: Response length: {len(r.text)} bytes")
        if r.status_code != 200:
            logger.error(f"OJApi: Response preview: {r.text[:500]}")
            raise RuntimeError(f"获取题目详情失败: HTTP {r.status_code} – {r.text[:200]}")
        
        logger.debug(f"OJApi: Response preview: {r.text[:200]}")
        data = r.json()
        
        if data.get("code") not in (0, 200):
            raise RuntimeError(f"API错误: {data.get('message') or data.get('msg', 'unknown error')}")
        return data.get("data", {}).get("problem", {})

    def upload_testcase_zip(self, auth: OJAuth, zip_path: str, mode: str = "default") -> Dict[str, Any]:
        """上传测试数据ZIP包（对应upload.py的do_upload）"""
        url = f"{self.api_base_url}/api/file/upload-testcase-zip?mode={mode}"
        
        # 读取文件数据
        with open(zip_path, "rb") as f:
            file_data = f.read()
        
        filename = os.path.basename(zip_path)
        
        # 构建WebKit风格的multipart/form-data（完全按照原始脚本）
        boundary = "----WebKitFormBoundary%08x%08x" % (int(time.time()) & 0xFFFFFFFF, os.getpid() & 0xFFFFFFFF)
        file_ct = "application/x-zip-compressed"
        crlf = "\r\n"
        
        # 构建multipart body
        lines = []
        lines.append(f"--{boundary}")
        lines.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"')
        lines.append(f"Content-Type: {file_ct}")
        lines.append("")
        
        body_head = crlf.join(lines).encode("utf-8") + crlf.encode("utf-8")
        body_tail = (crlf + f"--{boundary}--" + crlf).encode("utf-8")
        body = body_head + file_data + body_tail
        
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Accept": "*/*",
            "Origin": self.base_url.replace("-api", ""),
            "Referer": self.base_url.replace("-api", "") + "/",
            "User-Agent": "Mozilla/5.0",
            "authorization": auth.token,
            "url-type": "general",
        }
        
        r = auth.session.post(url, data=body, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        
        if r.status_code != 200:
            raise RuntimeError(f"Upload failed: HTTP {r.status_code} {r.reason}")
        
        json_resp = r.json()
        if json_resp.get("code") not in (0, 200):
            raise RuntimeError(f"Upload returned error: {json_resp}")
        
        return json_resp.get("data", {})

    def fetch_admin_problem(self, auth: OJAuth, pid: int) -> Dict[str, Any]:
        """获取题目配置（对应upload.py的fetch_problem）"""
        url = f"{self.api_base_url}/api/admin/problem?pid={pid}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
            "User-Agent": "Mozilla/5.0",
        }
        
        try:
            r = auth.session.get(url, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
            if r.status_code != 200:
                logger.warning(f"获取题目{pid}失败: HTTP {r.status_code} {r.reason}")
                return {}
            json_resp = r.json()
            return json_resp.get("data", {})
        except Exception as e:
            logger.warning(f"获取题目{pid}异常: {e}")
            return {}

    def fetch_problem_cases(self, auth: OJAuth, pid: int) -> List[Dict[str, Any]]:
        """触发服务器解析测试用例（对应upload.py的fetch_problem_cases）"""
        url = f"{self.api_base_url}/api/admin/problem/get-problem-cases?pid={pid}&isUpload=true"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
            "User-Agent": "Mozilla/5.0",
        }
        
        try:
            r = auth.session.get(url, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
            if r.status_code != 200:
                return []
            json_resp = r.json()
            return json_resp.get("data", []) or []
        except Exception:
            return []

    def put_admin_problem(self, auth: OJAuth, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新题目配置（对应upload.py的do_update）"""
        url = f"{self.api_base_url}/api/admin/problem"
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
            "Origin": self.base_url.replace("-api", ""),
            "Referer": self.base_url.replace("-api", "") + "/",
            "User-Agent": "Mozilla/5.0",
        }
        
        r = auth.session.put(url, data=data_bytes, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        
        if r.status_code != 200:
            # 尽量把后端返回的错误信息暴露出来，方便定位（例如缺少某个必需字段）
            detail = ""
            try:
                # 优先尝试解析JSON
                obj = r.json()
                msg = obj.get("message") or obj.get("msg") or ""
                code = obj.get("code")
                detail = f", code={code}, msg={msg}"
            except Exception:
                # 回退到原始文本
                try:
                    text_preview = r.text[:500]
                    detail = f", body={text_preview}"
                except Exception:
                    detail = ""
            raise RuntimeError(f"Update failed: HTTP {r.status_code} {r.reason}{detail}")
        
        return r.json()

    def submit_problem_judge(self, auth: OJAuth, original_id: str, code: str, language: str = "C++") -> int:
        """提交代码判题（对应solve.py的submit_code）"""
        url = f"{self.api_base_url}/api/submit-problem-judge"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": self.base_url.replace("-api", ""),
            "Referer": self.base_url.replace("-api", "") + "/",
            "Url-Type": "general",
            "User-Agent": "Mozilla/5.0 (compatible; ojo_batch_tool/1.0)",
        }
        payload = {
            "pid": str(original_id),
            "language": language,
            "code": code,
            "cid": 0,
            "tid": None,
            "gid": None,
            "isRemote": False,
        }
        
        r = auth.session.post(
            url, 
            headers=headers, 
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            timeout=self.timeout, 
            proxies=self.proxies, 
            verify=self.verify_ssl
        )
        
        if r.status_code != 200:
            raise RuntimeError(f"提交代码失败: HTTP {r.status_code} – {r.text.strip()}")
        
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"提交API错误: {data.get('message') or data.get('msg', 'unknown error')}")
        
        submit_id = data.get("data", {}).get("submitId")
        if not isinstance(submit_id, int):
            raise RuntimeError("响应中缺少submitId")
        
        return submit_id

    def get_submission_detail(self, auth: OJAuth, submit_id: int) -> Dict[str, Any]:
        """轮询提交详情（对应solve.py的poll_submission_detail）"""
        url = f"{self.api_base_url}/api/get-submission-detail?submitId={submit_id}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (compatible; ojo_batch_tool/1.0)",
            "Url-Type": "general",
            "Origin": self.base_url.replace("-api", ""),
            "Referer": self.base_url.replace("-api", "") + "/",
        }
        
        r = auth.session.get(url, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        
        if r.status_code != 200:
            raise RuntimeError(f"获取提交详情失败: HTTP {r.status_code} – {r.text.strip()}")
        
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"提交详情API错误: {data.get('message') or data.get('msg', 'unknown error')}")
        
        submission = data.get("data", {}).get("submission")
        if not submission:
            raise RuntimeError("响应中缺少submission详情")
        
        return submission
