# -*- coding: utf-8 -*-
"""HydroOJ解题提交实现"""

import re
import threading
import time
from html import unescape
from typing import Dict, Any, Optional
from urllib.parse import urljoin

from loguru import logger

from ...base.solution_submitter import SolutionSubmitter


class HydroOJSolutionSubmitter(SolutionSubmitter):
    """HydroOJ 解题提交器
    
    支持：
    - 提交代码到 HydroOJ 题目
    - 查询提交状态
    - 获取支持的编程语言列表
    """
    
    # 类级别的锁和时间戳，用于全局速率限制
    _submit_lock = threading.Lock()
    _last_submit_time = 0.0
    _min_submit_interval = 1.0  # 最小提交间隔（秒）
    
    def __init__(self, base_url: str, domain: str):
        """初始化提交器
        
        Args:
            base_url: HydroOJ 基础 URL（如 https://jooj.top）
            domain: 域名（如 polygon_test）
        """
        self.base_url = base_url.rstrip("/")
        self.domain = domain
    
    def fetch_submit_page(self, problem_id: str, auth: Any) -> str:
        """拉取提交页面
        
        Args:
            problem_id: 题目ID（HydroOJ 真实ID）
            auth: HydroOJAuth 认证对象
            
        Returns:
            提交页面 HTML
        """
        submit_url = f"{self.base_url}/d/{self.domain}/p/{problem_id}/submit"
        show_url = f"{self.base_url}/d/{self.domain}/p/{problem_id}"
        
        logger.debug(f"[HydroOJ Submit] 拉取提交页: {submit_url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ojo-submit/1.0)",
            "Referer": show_url,
        }
        
        r = auth.session.get(submit_url, headers=headers, timeout=30)
        r.raise_for_status()
        
        logger.debug(f"[HydroOJ Submit] 提交页响应: HTTP {r.status_code}, 长度: {len(r.text)}")
        
        return r.text
    
    def parse_lang_options(self, submit_html: str) -> Dict[str, str]:
        """解析提交页的语言选项
        
        Args:
            submit_html: 提交页 HTML
            
        Returns:
            语言映射 {"cc.cc20": "C++20", "py.py3": "Python 3", ...}
        """
        # 查找 <select name="lang">
        m = re.search(r'<select[^>]*name=["\']lang["\'][^>]*>(.*?)</select>', 
                     submit_html, flags=re.S | re.I)
        if not m:
            logger.warning("[HydroOJ Submit] 未找到语言选择框")
            return {}
        
        inner = m.group(1)
        options = re.findall(r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>', 
                            inner, flags=re.S | re.I)
        
        value_to_label: Dict[str, str] = {}
        for val, label_html in options:
            label = unescape(re.sub(r'\s+', ' ', label_html).strip())
            value = val.strip()
            value_to_label[value] = label
        
        logger.debug(f"[HydroOJ Submit] 解析到 {len(value_to_label)} 种语言")
        
        return value_to_label
    
    def submit_solution(self, problem_id: str, code: str, language: str, auth: Any) -> Dict[str, Any]:
        """提交解题代码
        
        Args:
            problem_id: 题目ID（HydroOJ 真实ID，即 real_id）
            code: 代码内容
            language: 语言键（如 "cc.cc20", "py.py3"）
            auth: HydroOJAuth 认证对象
            
        Returns:
            {
                "status": "success" | "error",
                "submission_id": "rid",  # 提交记录ID
                "record_url": "https://...",
                "message": "..."
            }
        """
        # 速率限制：确保每秒最多一个提交，且串行执行（整个提交过程都在锁内）
        with self._submit_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_submit_time
            
            if time_since_last < self._min_submit_interval:
                wait_time = self._min_submit_interval - time_since_last
                logger.debug(f"[HydroOJ Submit] 速率限制：等待 {wait_time:.2f} 秒后提交...")
                time.sleep(wait_time)
            
            # 记录本次提交开始时间
            submit_start_time = time.time()
            
            submit_url = f"{self.base_url}/d/{self.domain}/p/{problem_id}/submit"
            show_url = f"{self.base_url}/d/{self.domain}/p/{problem_id}"
            
            logger.info(f"[HydroOJ Submit] 提交到: {submit_url}")
            logger.debug(f"[HydroOJ Submit] 语言: {language}, 代码长度: {len(code)}")
            
            # 先访问题目页面，再访问提交页面，建立 session 并可能获取 CSRF token（与测试脚本保持一致）
            csrf_token = None
            try:
                page_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
                    "Referer": show_url,
                }
                
                # 先访问题目页面建立 session
                logger.debug(f"[HydroOJ Submit] 先访问题目页面建立 session...")
                show_r = auth.session.get(show_url, headers=page_headers, timeout=30)
                show_r.raise_for_status()
                logger.debug(f"[HydroOJ Submit] 题目页面响应: HTTP {show_r.status_code}")
                
                # 再访问提交页面
                page_headers["Referer"] = show_url
                logger.debug(f"[HydroOJ Submit] 访问提交页面...")
                page_r = auth.session.get(submit_url, headers=page_headers, timeout=30)
                page_r.raise_for_status()
                
                logger.debug(f"[HydroOJ Submit] 提交页面响应: HTTP {page_r.status_code}")
                
                # 尝试提取 CSRF token（多种可能的格式）
                # 方法1: <input name="csrfToken" value="...">
                csrf_match = re.search(r'<input[^>]*name=["\']csrfToken["\'][^>]*value=["\']([^"\']+)["\']', page_r.text)
                if csrf_match:
                    csrf_token = csrf_match.group(1)
                else:
                    # 方法2: <meta name="csrf-token" content="...">
                    csrf_match = re.search(r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']', page_r.text)
                    if csrf_match:
                        csrf_token = csrf_match.group(1)
                    else:
                        # 方法3: JavaScript 变量 csrfToken = "..."
                        csrf_match = re.search(r'csrfToken["\']?\s*[:=]\s*["\']([^"\']+)["\']', page_r.text)
                        if csrf_match:
                            csrf_token = csrf_match.group(1)
                
                if csrf_token:
                    logger.debug(f"[HydroOJ Submit] 提取到 CSRF token: {csrf_token[:20]}...")
                else:
                    logger.debug(f"[HydroOJ Submit] 未找到 CSRF token（可能不需要）")
                
                # 模拟用户行为：访问提交页面后稍微等待一下再提交
                time.sleep(0.5)
                    
            except Exception as e:
                logger.warning(f"[HydroOJ Submit] 获取提交页面失败: {e}，继续尝试提交")
            
            # POST 请求的 headers（注意：不要设置 Content-Type，让 requests 自动设置）
            headers = {
                "Origin": self.base_url,
                "Referer": submit_url,  # 与浏览器行为一致，Referer 指向提交页面
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "sec-ch-ua": '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document",
                "upgrade-insecure-requests": "1",
            }
            
            # 使用 multipart/form-data 格式提交（与浏览器行为一致）
            # 使用 files 参数可以让 requests 自动设置 Content-Type 为 multipart/form-data
            files = {
                "lang": (None, language),  # (filename, content) 格式，None 表示无文件
                "code": (None, code),
                "file": ("", ""),  # 空文件字段，与浏览器行为一致
            }
            
            # 如果获取到 CSRF token，添加到请求中
            if csrf_token:
                files["csrfToken"] = (None, csrf_token)
            
            # 检查 Cookie 是否正确设置
            logger.debug(f"[HydroOJ Submit] Session cookies: {[c.name for c in auth.session.cookies]}")
            if not auth.session.cookies:
                logger.warning(f"[HydroOJ Submit] 警告: Session 中没有 Cookie，可能导致认证失败")
            
            try:
                r = auth.session.post(
                    submit_url,
                    files=files,
                    headers=headers,
                    allow_redirects=False,
                    timeout=60
                )
                
                logger.debug(f"[HydroOJ Submit] 提交响应: HTTP {r.status_code}")
                logger.debug(f"[HydroOJ Submit] 响应 headers: {dict(r.headers)}")
                
                # 检查重定向
                if r.status_code in (301, 302, 303, 307, 308):
                    location = r.headers.get("Location", "")
                    logger.debug(f"[HydroOJ Submit] 重定向到: {location}")
                    
                    # 从 Location 提取 submission_id (rid)
                    # 格式: /d/{domain}/record/{rid}
                    record_url = urljoin(submit_url, location) if location else None
                    submission_id = None
                    
                    if location:
                        match = re.search(r'/record/([^/?]+)', location)
                        if match:
                            submission_id = match.group(1)
                            logger.info(f"[HydroOJ Submit] 提取到提交ID: {submission_id}")
                    
                    # 跟随重定向获取记录页
                    if record_url:
                        try:
                            r2 = auth.session.get(
                                record_url,
                                headers={
                                    "User-Agent": headers["User-Agent"],
                                    "Referer": submit_url
                                },
                                timeout=30
                            )
                            logger.debug(f"[HydroOJ Submit] 记录页响应: HTTP {r2.status_code}")
                        except Exception as e:
                            logger.warning(f"[HydroOJ Submit] 获取记录页失败: {e}")
                    
                    # 更新最后提交时间（提交完成）
                    self._last_submit_time = time.time()
                    submit_duration = self._last_submit_time - submit_start_time
                    logger.debug(f"[HydroOJ Submit] 提交完成，耗时 {submit_duration:.2f} 秒")
                    
                    if submission_id:
                        return {
                            "status": "success",
                            "submission_id": submission_id,
                            "record_url": record_url,
                            "message": f"提交成功，记录ID: {submission_id}"
                        }
                    else:
                        return {
                            "status": "success",
                            "record_url": record_url,
                            "message": "提交成功（未能提取记录ID）"
                        }
                elif r.status_code == 200:
                    # 直接返回 200，可能是提交页面有错误
                    logger.warning(f"[HydroOJ Submit] 提交返回 200，可能有错误")
                    self._last_submit_time = time.time()
                    return {
                        "status": "error",
                        "message": "提交可能失败（返回 200 而非重定向）"
                    }
                elif r.status_code == 403:
                    # 403 错误，输出更多调试信息
                    logger.error(f"[HydroOJ Submit] 提交失败: HTTP 403 Forbidden")
                    logger.error(f"[HydroOJ Submit] 请求 URL: {submit_url}")
                    logger.error(f"[HydroOJ Submit] 请求 headers: {dict(headers)}")
                    logger.error(f"[HydroOJ Submit] 请求 files keys: {list(files.keys())}")
                    logger.error(f"[HydroOJ Submit] Session cookies 详情:")
                    for cookie in auth.session.cookies:
                        logger.error(f"  - {cookie.name}={cookie.value[:30]}... domain={cookie.domain or '(auto)'} path={cookie.path or '(auto)'}")
                    
                    # 尝试读取响应内容（可能有错误信息）
                    try:
                        response_text = r.text[:1000] if r.text else "(空响应)"
                        logger.error(f"[HydroOJ Submit] 响应内容（前1000字符）: {response_text}")
                    except:
                        logger.error(f"[HydroOJ Submit] 无法读取响应内容")
                    
                    # 检查是否包含特定错误信息
                    if r.text and "Permission denied" in r.text:
                        logger.error(f"[HydroOJ Submit] 错误原因: 权限不足")
                    elif r.text and "Forbidden" in r.text:
                        logger.error(f"[HydroOJ Submit] 错误原因: 访问被拒绝")
                    elif r.text and "login" in r.text.lower():
                        logger.error(f"[HydroOJ Submit] 错误原因: 可能需要重新登录")
                    
                    self._last_submit_time = time.time()
                    return {
                        "status": "error",
                        "message": f"提交失败: HTTP 403 Forbidden（可能是认证问题或权限不足，请检查 Cookie 是否有效）"
                    }
                elif r.status_code == 429:
                    # 429 错误：请求过于频繁
                    retry_after = r.headers.get("Retry-After", "3")
                    try:
                        retry_seconds = int(retry_after)
                    except ValueError:
                        retry_seconds = 3
                    
                    logger.warning(f"[HydroOJ Submit] 提交失败: HTTP 429 Too Many Requests，建议等待 {retry_seconds} 秒")
                    # 更新最后提交时间，强制等待更长时间
                    self._last_submit_time = time.time() + retry_seconds
                    
                    return {
                        "status": "error",
                        "message": f"提交失败: HTTP 429 Too Many Requests（请求过于频繁，建议等待 {retry_seconds} 秒）"
                    }
                else:
                    logger.error(f"[HydroOJ Submit] 提交失败: HTTP {r.status_code}")
                    logger.debug(f"[HydroOJ Submit] 响应内容: {r.text[:500]}")
                    self._last_submit_time = time.time()
                    return {
                        "status": "error",
                        "message": f"提交失败: HTTP {r.status_code}"
                    }
                    
            except Exception as e:
                logger.error(f"[HydroOJ Submit] 提交异常: {e}")
                self._last_submit_time = time.time()
                return {
                    "status": "error",
                    "message": f"提交异常: {str(e)}"
                }
    
    def get_submission_status(self, submission_id: str, auth: Any) -> Dict[str, Any]:
        """查询提交状态（轻量实现）
        
        Args:
            submission_id: 提交记录ID（rid）
            auth: HydroOJAuth 认证对象
            
        Returns:
            {
                "status": "Judging" | "Accepted" | "Wrong Answer" | ...,
                "record_url": "https://...",
                "message": "..."
            }
        """
        record_url = f"{self.base_url}/d/{self.domain}/record/{submission_id}"
        
        logger.debug(f"[HydroOJ Submit] 查询提交状态: {record_url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ojo-submit/1.0)",
        }
        
        try:
            r = auth.session.get(record_url, headers=headers, timeout=30)
            r.raise_for_status()
            
            logger.debug(f"[HydroOJ Submit] 记录页响应: HTTP {r.status_code}")
            
            # 从页面文本获取判题状态和分数
            page = r.text or ""
            verdict = None
            score = None
            
            # 优先提取分数和整体状态（从 section__header 中）
            # 查找 <span style="color: #xxxxx">80</span> 这样的分数
            score_match = re.search(r'<span[^>]*style="color:\s*[^"]*"[^>]*>(\d+)</span>\s*<span[^>]*class="record-status--text[^"]*"[^>]*>\s*(\w+(?:\s+\w+)*)\s*</span>', page, re.I)
            if score_match:
                score = int(score_match.group(1))
                verdict = score_match.group(2).strip()
                logger.info(f"[HydroOJ Submit] 检测到分数: {score}, 状态: {verdict}")
            else:
                # 备用方案：查找 record-status--text 中的状态
                status_match = re.search(r'<span[^>]*class="record-status--text[^"]*"[^>]*>\s*(\w+(?:\s+\w+)*)\s*</span>', page, re.I)
                if status_match:
                    verdict = status_match.group(1).strip()
                    logger.info(f"[HydroOJ Submit] 检测到状态: {verdict}")
            
            # 如果没有提取到，使用关键字搜索（向后兼容）
            if not verdict:
                status_keywords = [
                    "Accepted",
                    "Wrong Answer",
                    "Time Limit Exceeded",
                    "Memory Limit Exceeded",
                    "Runtime Error",
                    "Compile Error",
                    "System Error",
                    "Judging",
                    "Waiting",
                    "Pending",
                ]
                
                for kw in status_keywords:
                    if kw.lower() in page.lower():
                        verdict = kw
                        logger.info(f"[HydroOJ Submit] 通过关键字检测到状态: {verdict}")
                        break
            
            if verdict:
                # 判断是否完全通过（分数为100或状态为Accepted且无分数信息）
                is_accepted = (score == 100 if score is not None else verdict == "Accepted")
                
                return {
                    "status": verdict,
                    "score": score,
                    "is_accepted": is_accepted,
                    "record_url": record_url,
                    "message": f"判题状态: {verdict}" + (f" ({score}分)" if score is not None else "")
                }
            else:
                return {
                    "status": "Unknown",
                    "record_url": record_url,
                    "message": "无法确定判题状态"
                }
                
        except Exception as e:
            logger.error(f"[HydroOJ Submit] 查询状态异常: {e}")
            return {
                "status": "Error",
                "message": f"查询异常: {str(e)}"
            }
    
    def get_language_map(self, problem_id: Optional[str] = None, auth: Any = None) -> Dict[str, str]:
        """获取支持的编程语言映射（扩展功能）
        
        Args:
            problem_id: 题目ID（可选，如提供则从提交页动态获取）
            auth: HydroOJAuth 认证对象（可选）
            
        Returns:
            语言映射 {"cc.cc20": "C++20", "py.py3": "Python 3", ...}
        """
        # 如果提供了 problem_id 和 auth，尝试动态获取
        if problem_id and auth:
            try:
                submit_html = self.fetch_submit_page(problem_id, auth)
                langs = self.parse_lang_options(submit_html)
                if langs:
                    logger.debug(f"[HydroOJ Submit] 从提交页获取到 {len(langs)} 种语言")
                    return langs
            except Exception as e:
                logger.warning(f"[HydroOJ Submit] 动态获取语言失败: {e}")
        
        # 返回常见语言的静态列表
        static_langs = {
            "c": "C",
            "cc": "C++",
            "cc.cc98": "C++98",
            "cc.cc11": "C++11",
            "cc.cc14": "C++14",
            "cc.cc17": "C++17",
            "cc.cc20": "C++20",
            "py.py3": "Python 3",
            "py.py2": "Python 2",
            "java": "Java",
            "pas": "Pascal",
            "js": "JavaScript",
            "go": "Go",
            "rust": "Rust",
        }
        
        logger.debug(f"[HydroOJ Submit] 返回静态语言列表 ({len(static_langs)} 种)")
        return static_langs
    
    def supported_languages(self) -> list[str]:
        """获取支持的编程语言列表（基类接口）
        
        Returns:
            语言键列表
        """
        lang_map = self.get_language_map()
        return list(lang_map.keys())
    
    def get_default_language(self, lang_hint: str = "C++") -> str:
        """获取默认语言键
        
        Args:
            lang_hint: 语言提示（如 "C++", "Python"）
            
        Returns:
            HydroOJ 使用的语言键
        """
        hint_lower = lang_hint.lower()
        if "c++" in hint_lower or "cpp" in hint_lower:
            return "cc.cc17o2"  # C++17 with O2
        elif "python" in hint_lower or "py" in hint_lower:
            return "py.py3"
        elif "java" in hint_lower:
            return "java"
        else:
            return "cc.cc17o2"  # 默认 C++
