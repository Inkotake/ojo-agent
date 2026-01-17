# -*- coding: utf-8 -*-
"""Aicoders 题面获取实现"""

from typing import Dict, Any, Optional
import json, re
from loguru import logger
import requests

from ...base.problem_fetcher import ProblemFetcher


class AicodersProblemFetcher(ProblemFetcher):
    """Aicoders 题面获取器"""
    
    def __init__(self, base_url: str, timeout: int, proxies: dict = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxies = proxies
        self.verify_ssl = verify_ssl
        # 固定使用 Aicoders 的 API URL
        self.api_base_url = "https://api-tcoj.aicoders.cn"
    
    def supports_url(self, url: str) -> bool:
        """判断是否支持该URL（仅支持 aicoders.cn）"""
        url_lower = url.lower()
        return (
            'oj.aicoders.cn' in url_lower or 
            'aicoders.cn' in url_lower or
            'api-tcoj.aicoders.cn' in url_lower
        )
    
    def parse_problem_id(self, input_str: str) -> Optional[str]:
        """从URL或ID字符串中解析题目ID
        
        支持格式:
        - 纯ID: "1234"
        - URL: "https://oj.aicoders.cn/problem/1234"
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
        
        logger.warning(f"无法解析 Aicoders 题目ID: {input_str}")
        return None
    
    def fetch_problem(self, problem_id: str) -> Dict[str, Any]:
        """获取题目信息，返回标准格式"""
        # 调用 Aicoders API
        raw_data = self.get_problem_detail(problem_id)
        
        # 转换为标准格式
        return self._convert_to_standard(raw_data, problem_id)
    
    def get_problem_detail(self, original_id: str) -> Dict[str, Any]:
        """获取公开题目详情（Aicoders API）"""
        url = f"{self.api_base_url}/api/get-problem-detail?problemId={original_id}"
        headers = {"url-type": "general"}
        
        logger.info(f"Aicoders: 请求题目详情 {original_id}")
        logger.debug(f"Aicoders: URL: {url}")
        
        r = requests.get(url, headers=headers, timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        r.raise_for_status()
        data = r.json()
        
        if data.get("code") not in (0, 200):
            raise RuntimeError(f"获取题目详情失败: {data}")
        
        # API返回的data包含problem、tags、languages等字段
        full_data = data.get("data", {})
        
        # 将tags和languages添加到problem对象中
        problem = full_data.get("problem", {})
        
        logger.debug(f"[Aicoders] 题目 {original_id} - full_data 中的 tags: {full_data.get('tags', 'NOT_FOUND')}")
        logger.debug(f"[Aicoders] 题目 {original_id} - problem 中的 tags: {problem.get('tags', 'NOT_FOUND')}")

        # 优先使用外层的tags，如果外层不存在或为空则保留problem内部的tags
        if "tags" in full_data:
            # 外层有tags字段（无论是否为空），优先使用外层的
            problem["tags"] = full_data["tags"]
            logger.debug(f"[Aicoders] 题目 {original_id} - 使用 full_data 的 tags: {problem['tags']}")
        # 如果外层没有tags字段，保留problem内部的tags（如果有的话）
        elif "tags" not in problem:
            problem["tags"] = []
            logger.debug(f"[Aicoders] 题目 {original_id} - problem 内部无 tags，设置为空列表")
        else:
            logger.debug(f"[Aicoders] 题目 {original_id} - 保留 problem 内部的 tags: {problem['tags']}")
        
        return problem
    
    def _convert_to_standard(self, raw_data: Dict[str, Any], problem_id: str) -> Dict[str, Any]:
        """将 Aicoders API 响应转换为标准格式
        
        Args:
            raw_data: API 返回的原始数据
            problem_id: 题目ID
            
        Returns:
            标准格式的题目数据字典
        """
        # 解析样例（XML 格式）
        samples = []
        examples_data = raw_data.get("examples") or raw_data.get("samples") or ""
        
        if examples_data:
            try:
                if isinstance(examples_data, str) and examples_data.strip().startswith('<'):
                    # XML 格式解析
                    import re
                    input_match = re.search(r'<input>(.*?)</input>', examples_data, re.DOTALL)
                    output_match = re.search(r'<output>(.*?)</output>', examples_data, re.DOTALL)
                    
                    if input_match and output_match:
                        input_text = input_match.group(1)
                        output_text = output_match.group(1)
                        
                        # 处理转义的换行符
                        input_text = input_text.replace('\\n', '\n')
                        output_text = output_text.replace('\\n', '\n')
                        
                        samples.append({
                            "input": input_text,
                            "output": output_text
                        })
                        logger.debug(f"[Aicoders] XML格式样例解析成功")
            except Exception as e:
                logger.debug(f"解析样例失败: {e}")
        
        # 处理标签
        tags_raw = raw_data.get("tags", [])
        tags = []
        
        if isinstance(tags_raw, list):
            for tag_obj in tags_raw:
                if isinstance(tag_obj, dict):
                    tag_name = tag_obj.get("name")
                    if tag_name:
                        tags.append(tag_name)
                elif isinstance(tag_obj, str):
                    tags.append(tag_obj)
        
        # 构建标准格式
        standard_data = {
            "id": problem_id,
            "source": "aicoders",
            "title": raw_data.get("title", ""),
            "description": raw_data.get("description", ""),
            "input_format": raw_data.get("input") or raw_data.get("inputFormat", ""),
            "output_format": raw_data.get("output") or raw_data.get("outputFormat", ""),
            "samples": samples,
            "time_limit": raw_data.get("timeLimit", 1000),
            "memory_limit": raw_data.get("memoryLimit", 256),
            "difficulty": str(raw_data.get("difficulty", 0)),
            "tags": tags,
            "hints": raw_data.get("hint", ""),
            "author": raw_data.get("author", ""),
            "url": f"https://oj.aicoders.cn/problem/{problem_id}",
            "extra": {
                "oj_type": "aicoders",
                "raw_data": raw_data  # 保留原始数据
            }
        }
        
        return standard_data

