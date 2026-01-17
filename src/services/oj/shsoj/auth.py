# -*- coding: utf-8 -*-
"""SHSOJ认证模块"""

from __future__ import annotations
from dataclasses import dataclass
import requests
from loguru import logger
from utils.concurrency import retry_with_backoff


# SHSOJ 固定 API 地址（不需要用户配置）
SHSOJ_API_URL = "https://oj-api.shsbnu.net"


@dataclass
class OJAuth:
    """OJ认证信息"""
    token: str
    session: requests.Session


class SHSOJAuth:
    """SHSOJ认证实现"""
    
    def __init__(self, base_url: str = "", timeout: int = 300, 
                 proxies: dict | None = None, verify_ssl: bool = True):
        # base_url 参数保留向后兼容，但实际使用固定的 API 地址
        self.base_url = SHSOJ_API_URL
        self.timeout = timeout
        self.proxies = proxies or None
        self.verify_ssl = verify_ssl
    
    def login_user(self, username: str, password: str) -> OJAuth:
        """登录并获取token
        
        使用固定的 API 地址：https://oj-api.shsbnu.net/api/login
        """
        url = f"{self.base_url}/api/login"
        
        s = requests.Session()
        s.proxies = self.proxies or {}
        
        # 简化 headers，只保留必要的
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
        }
        payload = {"username": username, "password": password}
        
        # 添加详细日志
        logger.debug(f"[SHSOJ] 登录请求 URL: {url}")
        logger.debug(f"[SHSOJ] 登录用户名: {username}，密码长度: {len(password)}")

        def _req():
            resp = s.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=self.timeout, 
                proxies=self.proxies, 
                verify=self.verify_ssl
            )
            
            if resp.status_code != 200:
                logger.error(f"[SHSOJ] 登录失败，HTTP状态 {resp.status_code}")
                logger.error(f"[SHSOJ] 响应内容: {resp.text[:500]}")
                raise RuntimeError(f"登录失败，HTTP状态 {resp.status_code}: {resp.text}")
            
            # 解析响应
            try:
                data = resp.json()
            except Exception as e:
                raise RuntimeError(f"登录响应解析失败: {e}")
            
            # 检查业务状态码（code 或 status 字段）
            business_code = data.get("code") or data.get("status")
            if business_code not in (0, 200):
                error_msg = data.get("msg") or data.get("message") or "未知错误"
                logger.error(f"[SHSOJ] 登录失败，业务状态码 {business_code}: {error_msg}")
                logger.error(f"[SHSOJ] 响应体: {resp.text[:500]}")
                raise RuntimeError(f"登录失败: {error_msg}")
            
            # 尝试从响应头获取 token
            token = resp.headers.get("Authorization") or resp.headers.get("authorization")
            
            # 如果响应头没有，尝试从响应体获取
            if not token:
                token = (
                    data.get("data", {}).get("token") if isinstance(data.get("data"), dict) else None
                ) or data.get("token") or (
                    data.get("data", {}).get("Authorization") if isinstance(data.get("data"), dict) else None
                ) or data.get("Authorization")
                logger.debug(f"[SHSOJ] 从响应体获取 token: {'成功' if token else '失败'}")
            
            if not token:
                logger.error(f"[SHSOJ] 登录响应头: {dict(resp.headers)}")
                logger.error(f"[SHSOJ] 登录响应体: {resp.text[:500]}")
                raise RuntimeError("登录成功但未返回Authorization token")
            
            s.headers.update({"authorization": token, "url-type": "general"})
            logger.info(f"[SHSOJ] 登录成功，token 前缀: {token[:20]}...")
            return token

        token = retry_with_backoff(_req, on_error=lambda e, a: logger.warning(f"[SHSOJ] 登录重试 {a}: {e}"))
        return OJAuth(token=token, session=s)
