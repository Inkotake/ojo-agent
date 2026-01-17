# -*- coding: utf-8 -*-
"""SHSOJ题面获取实现（适配新接口）"""

from typing import Dict, Any, Optional
import json, re
from loguru import logger
import requests

from ...base.problem_fetcher import ProblemFetcher
from .url_utils import derive_api_url


class SHSOJProblemFetcher(ProblemFetcher):
    """SHSOJ题面获取器（实现新接口）"""
    
    def __init__(self, base_url: str, timeout: int, proxies: dict = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxies = proxies
        self.verify_ssl = verify_ssl
        # 推导API URL（前端URL → API URL）
        self.api_base_url = derive_api_url(self.base_url)
    
    def supports_url(self, url: str) -> bool:
        """判断是否支持该URL（仅支持 shsbnu.net）
        
        支持的URL格式：
        - 前端: https://oj.shsbnu.net/problem/xxx
        - API: https://oj-api.shsbnu.net/api/get-problem-detail?problemId=xxx
        """
        url_lower = url.lower()
        return (
            'shsbnu.net' in url_lower or 
            'oj.shs' in url_lower or
            'oj-api.shsbnu.net' in url_lower
        )
    
    def parse_problem_id(self, input_str: str) -> Optional[str]:
        """从URL或ID字符串中解析题目ID
        
        支持格式:
        - 纯ID: "1234"
        - URL: "https://oj.shsbnu.net/problem/1234"
        """
        input_str = input_str.strip()
        
        # 尝试从URL中提取
        if 'http' in input_str:
            # 匹配 /problem/1234 格式
            match = re.search(r'/problem/(\d+)', input_str)
            if match:
                return match.group(1)
        
        # 直接是ID
        if input_str.isdigit():
            return input_str
        
        logger.warning(f"无法解析SHSOJ题目ID: {input_str}")
        return None
    
    def fetch_problem(self, problem_id: str) -> Dict[str, Any]:
        """获取题目信息，返回标准格式
        
        这里返回的是标准格式，方便后续转换为ProblemMetadata
        """
        # 调用SHSOJ API
        raw_data = self.get_problem_detail(problem_id)
        
        # 转换为标准格式
        return self._convert_to_standard(raw_data, problem_id)
    
    def fetch_admin_problem(self, auth, pid: int) -> Dict[str, Any]:
        """获取管理员题目信息（需要登录凭证）
        
        Args:
            auth: 认证对象，包含 token 和 session
            pid: 题目ID
            
        Returns:
            题目配置数据
        """
        url = f"{self.api_base_url}/api/admin/problem?pid={pid}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
            "User-Agent": "Mozilla/5.0 (compatible; ojo_tool/1.0)",
        }
        
        r = auth.session.get(
            url, 
            headers=headers, 
            timeout=self.timeout, 
            proxies=self.proxies, 
            verify=self.verify_ssl
        )
        r.raise_for_status()
        
        # 某些情况下返回HTML登陆页，需显式校验
        ct = (r.headers.get("Content-Type") or "").lower()
        if "application/json" not in ct:
            logger.warning(f"fetch_admin_problem 非JSON响应，Content-Type={ct}，预览: {r.text[:200]}")
            raise RuntimeError("后端返回非JSON内容，可能未通过鉴权或网关拦截")
        
        data = r.json()
        
        if data.get("code") not in (0, 200):
            raise RuntimeError(f"获取管理员题目失败: {data}")
        
        return data.get("data", {})
    
    def get_problem_detail(self, original_id: str) -> Dict[str, Any]:
        """获取公开题目详情（SHSOJ原生API）"""
        # 使用推导的API URL
        url = f"{self.api_base_url}/api/get-problem-detail?problemId={original_id}"
        headers = {"url-type": "general"}
        
        logger.info(f"SHSOJ: 请求题目详情 {original_id}")
        logger.info(f"SHSOJ: 使用 API URL: {url}")
        logger.info(f"SHSOJ: base_url={self.base_url}, api_base_url={self.api_base_url}")
        
        r = requests.get(url, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        logger.info(f"SHSOJ: HTTP {r.status_code}, Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        logger.info(f"SHSOJ: Response length: {len(r.text)} bytes")
        logger.info(f"SHSOJ: Response preview: {r.text[:200]}")
        
        r.raise_for_status()
        data = r.json()
        
        if data.get("code") not in (0, 200):
            raise RuntimeError(f"获取题目详情失败: {data}")
        
        # API返回的data包含problem、tags、languages等字段
        # 我们需要合并这些字段以便后续处理
        full_data = data.get("data", {})
        
        # 将tags和languages添加到problem对象中
        problem = full_data.get("problem", {})
        
        # 调试日志：记录合并前的状态
        logger.debug(f"[SHSOJ] 题目 {original_id} - full_data 中的 tags: {full_data.get('tags', 'NOT_FOUND')}")
        logger.debug(f"[SHSOJ] 题目 {original_id} - problem 中的 tags: {problem.get('tags', 'NOT_FOUND')}")
        
        # 优先使用外层的tags，如果外层不存在或为空则保留problem内部的tags
        if "tags" in full_data:
            # 外层有tags字段（无论是否为空），优先使用外层的
            problem["tags"] = full_data["tags"]
            logger.debug(f"[SHSOJ] 题目 {original_id} - 使用 full_data 的 tags: {problem['tags']}")
        # 如果外层没有tags字段，保留problem内部的tags（如果有的话）
        # 如果problem内部也没有，确保有一个空列表
        elif "tags" not in problem:
            problem["tags"] = []
            logger.debug(f"[SHSOJ] 题目 {original_id} - problem 内部无 tags，设置为空列表")
        else:
            logger.debug(f"[SHSOJ] 题目 {original_id} - 保留 problem 内部的 tags: {problem['tags']}")
        
        # 同样处理languages
        if "languages" in full_data:
            problem["languages"] = full_data["languages"]
        if "languages" not in problem:
            problem["languages"] = []
        
        return problem
    
    def _convert_to_standard(self, raw_data: Dict[str, Any], problem_id: str) -> Dict[str, Any]:
        """将SHSOJ原始数据转换为标准格式
        
        Args:
            raw_data: SHSOJ API返回的原始数据
            problem_id: 题目ID
            
        Returns:
            标准格式的题目数据字典
        """
        # 解析样例
        samples = []
        examples_data = raw_data.get("examples") or raw_data.get("samples") or ""
        
        # SHSOJ的样例格式：XML格式字符串或JSON数组
        if examples_data:
            try:
                if isinstance(examples_data, str):
                    # 尝试XML解析（SHSOJ格式）
                    if examples_data.strip().startswith('<'):
                        import re
                        # 提取 <input>...</input> 和 <output>...</output>
                        input_match = re.search(r'<input>(.*?)</input>', examples_data, re.DOTALL)
                        output_match = re.search(r'<output>(.*?)</output>', examples_data, re.DOTALL)
                        
                        if input_match and output_match:
                            input_text = input_match.group(1)
                            output_text = output_match.group(1)
                            
                            # 处理转义的换行符：将 \n 转为实际换行符
                            # 但要保留原始的空格和格式
                            input_text = input_text.replace('\\n', '\n')
                            output_text = output_text.replace('\\n', '\n')
                            
                            samples.append({
                                "input": input_text,
                                "output": output_text
                            })
                            logger.debug(f"[SHSOJ] XML格式样例解析成功，input长度={len(input_text)}, output长度={len(output_text)}")
                    else:
                        # 尝试JSON解析
                        examples_list = json.loads(examples_data)
                        for ex in examples_list:
                            if isinstance(ex, dict):
                                samples.append({
                                    "input": str(ex.get("input", "")),
                                    "output": str(ex.get("output", ""))
                                })
                else:
                    # 直接是数组
                    examples_list = examples_data
                    for ex in examples_list:
                        if isinstance(ex, dict):
                            samples.append({
                                "input": str(ex.get("input", "")),
                                "output": str(ex.get("output", ""))
                            })
            except Exception as e:
                logger.debug(f"解析样例失败: {e}")
                logger.exception("样例解析异常详情:")
        
        # 处理标签：从对象数组提取名称
        tags_raw = raw_data.get("tags", [])
        tags = []
        
        logger.debug(f"[SHSOJ] 题目 {problem_id} 原始标签数据: {tags_raw}")
        
        if isinstance(tags_raw, list):
            for tag_obj in tags_raw:
                if isinstance(tag_obj, dict):
                    tag_name = tag_obj.get("name")
                    if tag_name:
                        tags.append(tag_name)
                elif isinstance(tag_obj, str):
                    tags.append(tag_obj)
        
        logger.debug(f"[SHSOJ] 题目 {problem_id} 提取的标签: {tags}")
        
        # 构建标准格式
        standard_data = {
            "id": problem_id,
            "source": "shsoj",
            "title": raw_data.get("title", ""),
            "description": raw_data.get("description", ""),
            "input_format": raw_data.get("input") or raw_data.get("inputFormat", ""),
            "output_format": raw_data.get("output") or raw_data.get("outputFormat", ""),
            "samples": samples,
            "time_limit": raw_data.get("timeLimit"),
            "memory_limit": raw_data.get("memoryLimit"),
            "difficulty": str(raw_data.get("difficulty", "")),
            "tags": tags,
            "hints": raw_data.get("hint", ""),
            "author": raw_data.get("author", ""),
            "url": f"{self.base_url}/problem/{problem_id}",
            "extra": {
                "oj_type": "shsoj",
                "raw_data": raw_data  # 保留原始数据以备后用
            }
        }
        
        return standard_data

