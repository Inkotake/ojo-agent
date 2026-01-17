# -*- coding: utf-8 -*-
"""HydroOJ认证模块"""

import json
import sys
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests


class HydroOJAuth:
    """HydroOJ认证（基于Cookie）"""
    
    def __init__(self, base_url: str, domain: str):
        self.base_url = base_url.rstrip("/")
        self.domain = domain
        self.session = requests.Session()
    
    def login_with_selenium(self, login_url: str = None, target_domain: str = None) -> str:
        """使用Selenium自动登录获取Cookie
        
        Args:
            login_url: 登录URL，默认为 base_url/login
            target_domain: 目标域名，默认为 base_url 的域名
            
        Returns:
            Cookie字符串 (sid=...; sid.sig=...)
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError:
            raise ImportError("需要安装selenium和webdriver-manager: pip install selenium webdriver-manager")
        
        login_url = login_url or f"{self.base_url}/login"
        target_domain = target_domain or self._extract_domain()
        
        # 启动Chrome
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        
        try:
            driver.get(login_url)
            print(f"[i] 请在打开的Chrome窗口中完成 {target_domain} 登录。完成后回到此终端按回车。")
            input()
            
            # 获取Cookies
            raw_cookies = driver.get_cookies()
            
            # 筛选目标域名的Cookies
            cookies = [c for c in raw_cookies if target_domain in (c.get("domain") or "")]
            
            # 构建Cookie字符串
            cookie_parts = []
            for c in cookies:
                cookie_parts.append(f"{c['name']}={c['value']}")
            
            cookie_str = "; ".join(cookie_parts)
            
            # 保存到本地（可选）
            cookie_file = Path("hydrooj_cookies.json")
            cookie_file.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
            print(f"[✓] 已保存 {len(cookies)} 条 cookies -> hydrooj_cookies.json")
            
            # 加载到session
            self.load_cookies_from_driver(cookies)
            
            return cookie_str
        finally:
            driver.quit()
    
    def load_cookies_from_driver(self, cookies: list):
        """从Selenium Cookies列表加载到session"""
        for cookie in cookies:
            self.session.cookies.set(
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', ''),
                path=cookie.get('path', '/')
            )
    
    def load_cookies_from_file(self, cookie_file: Path = None) -> bool:
        """从文件加载Cookies"""
        cookie_file = cookie_file or Path("hydrooj_cookies.json")
        if not cookie_file.exists():
            return False
        
        try:
            cookies = json.loads(cookie_file.read_text())
            self.load_cookies_from_driver(cookies)
            return True
        except Exception:
            return False
    
    def login_with_cookie(self, cookie_str: str):
        """使用Cookie字符串登录
        
        Args:
            cookie_str: 'sid=xxx; sid.sig=yyy' 格式的Cookie字符串
            
        Returns:
            self (链式调用)
        """
        from loguru import logger
        
        cookies = self._parse_cookie(cookie_str)
        domain = self._extract_domain()
        
        logger.debug(f"[HydroOJ Auth] Cookie 字符串长度: {len(cookie_str)}")
        logger.debug(f"[HydroOJ Auth] 解析的 Cookie 键: {list(cookies.keys())}")
        logger.debug(f"[HydroOJ Auth] 提取的 domain: {domain}")
        
        for name, value in cookies.items():
            logger.debug(f"[HydroOJ Auth] 设置 Cookie: {name}={value[:20]}... (长度:{len(value)})")
            # 不设置 domain，让 requests 自动处理（与参考脚本一致）
            self.session.cookies.set(name, value)
        
        # 验证 Cookie 是否已设置
        logger.debug(f"[HydroOJ Auth] Session Cookie 总数: {len(self.session.cookies)}")
        for cookie in self.session.cookies:
            logger.debug(f"[HydroOJ Auth]   - {cookie.name}={cookie.value[:20]}... domain={cookie.domain} path={cookie.path}")
        
        return self
    
    def _parse_cookie(self, cookie_str: str) -> Dict[str, str]:
        """解析Cookie字符串
        
        Args:
            cookie_str: 'k1=v1; k2=v2' 格式
            
        Returns:
            Cookie字典
        """
        result = {}
        for pair in cookie_str.split(';'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                result[k.strip()] = v.strip()
        return result
    
    def _extract_domain(self) -> str:
        """从base_url提取域名"""
        parsed = urlparse(self.base_url)
        return parsed.netloc

