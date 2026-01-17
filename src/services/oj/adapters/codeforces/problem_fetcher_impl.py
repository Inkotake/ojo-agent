# -*- coding: utf-8 -*-
"""Codeforces题面获取实现"""

from typing import Dict, Any, Optional
import re
import requests
from bs4 import BeautifulSoup
from loguru import logger

from ...base.problem_fetcher import ProblemFetcher


class CodeforcesProblemFetcher(ProblemFetcher):
    """Codeforces题面获取器"""
    
    def __init__(self):
        self.timeout = 30
    
    def supports_url(self, url: str) -> bool:
        """判断是否支持该URL"""
        return 'codeforces.com' in url.lower()
    
    def parse_problem_id(self, input_str: str) -> Optional[str]:
        """从URL或ID字符串中解析题目ID
        
        支持格式:
        - URL: https://codeforces.com/problemset/problem/1234/A
        - URL: https://codeforces.com/contest/1234/problem/A
        - ID: 1234A
        """
        input_str = input_str.strip()
        
        # 从URL中提取
        if 'http' in input_str:
            # 匹配 /problem/1234/A 或 /contest/1234/problem/A
            match = re.search(r'/problem/(\d+)/([A-Z]\d?)', input_str)
            if not match:
                match = re.search(r'/contest/(\d+)/problem/([A-Z]\d?)', input_str)
            
            if match:
                return f"{match.group(1)}{match.group(2)}"
        
        # 直接是ID (如 1234A)
        if re.match(r'^\d+[A-Z]\d?$', input_str):
            return input_str
        
        logger.warning(f"无法解析Codeforces题目ID: {input_str}")
        return None
    
    def fetch_problem(self, problem_id: str) -> Dict[str, Any]:
        """获取题目信息
        
        Args:
            problem_id: 题目ID（如 1234A）
            
        Returns:
            标准格式的题目数据
        """
        contest_id, letter = self._split_problem_id(problem_id)
        
        # 构建URL（尝试problemset和contest两种）
        url = f"https://codeforces.com/problemset/problem/{contest_id}/{letter}"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 404:
                # 尝试contest URL
                url = f"https://codeforces.com/contest/{contest_id}/problem/{letter}"
                response = requests.get(url, timeout=self.timeout)
            
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"获取Codeforces题目失败: {e}")
        
        # 解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        return self._parse_problem_page(soup, problem_id, url)
    
    def _split_problem_id(self, problem_id: str) -> tuple[str, str]:
        """分割题目ID为contest_id和letter
        
        Args:
            problem_id: 如 "1234A"
            
        Returns:
            (contest_id, letter) 如 ("1234", "A")
        """
        match = re.match(r'^(\d+)([A-Z]\d?)$', problem_id)
        if not match:
            raise ValueError(f"无效的Codeforces题目ID: {problem_id}")
        return match.group(1), match.group(2)
    
    def _parse_problem_page(self, soup: BeautifulSoup, problem_id: str, url: str) -> Dict[str, Any]:
        """解析题目页面HTML
        
        Args:
            soup: BeautifulSoup对象
            problem_id: 题目ID
            url: 题目URL
            
        Returns:
            标准格式的题目数据
        """
        # 提取标题
        title_div = soup.select_one('.problem-statement .title')
        title = title_div.get_text().strip() if title_div else ""
        # 移除题号前缀（如 "A. "）
        title = re.sub(r'^[A-Z]\d?\.\s*', '', title)
        
        # 提取时间和内存限制（更精确的提取）
        time_limit_div = soup.select_one('.time-limit')
        memory_limit_div = soup.select_one('.memory-limit')
        
        time_limit = None
        if time_limit_div:
            time_text = time_limit_div.get_text()
            # 支持小数，如 "2.5 seconds" 或 "2 seconds"
            match = re.search(r'([\d.]+)\s*second', time_text, re.IGNORECASE)
            if match:
                time_sec = float(match.group(1))
                time_limit = int(time_sec * 1000)  # 转换为毫秒
            else:
                # 备用：只提取数字
                match = re.search(r'(\d+)', time_text)
                if match:
                    time_limit = int(match.group(1)) * 1000
        
        memory_limit = None
        if memory_limit_div:
            mem_text = memory_limit_div.get_text()
            # 支持 MB 或 GB
            match = re.search(r'([\d.]+)\s*(MB|GB|megabyte|gigabyte)', mem_text, re.IGNORECASE)
            if match:
                mem_value = float(match.group(1))
                unit = match.group(2).upper()
                if 'GB' in unit or 'gigabyte' in unit.lower():
                    memory_limit = int(mem_value * 1024)  # 转换为MB
                else:
                    memory_limit = int(mem_value)
            else:
                # 备用：只提取数字，假设为MB
                match = re.search(r'(\d+)', mem_text)
                if match:
                    memory_limit = int(match.group(1))
        
        # 提取题目描述、输入、输出格式
        statement_divs = soup.select('.problem-statement > div')
        
        description = ""
        input_format = ""
        output_format = ""
        
        for div in statement_divs:
            header = div.select_one('.section-title')
            if not header:
                continue
            
            header_text = header.get_text().strip().lower()
            content = div.get_text().replace(header.get_text(), '').strip()
            
            if 'input' in header_text:
                input_format = content
            elif 'output' in header_text:
                output_format = content
            elif not description and header_text:
                # 第一个有标题的section通常是题目描述
                description = content
        
        # 如果没找到独立的描述区域，使用整个problem-statement
        if not description:
            desc_div = soup.select_one('.problem-statement')
            if desc_div:
                description = desc_div.get_text().strip()
        
        # 提取样例
        samples = []
        sample_divs = soup.select('.sample-test')
        if sample_divs:
            inputs = sample_divs[0].select('.input pre')
            outputs = sample_divs[0].select('.output pre')
            
            for inp, out in zip(inputs, outputs):
                samples.append({
                    "input": inp.get_text().strip(),
                    "output": out.get_text().strip()
                })
        
        # 构建标准格式
        return {
            "id": problem_id,
            "source": "codeforces",
            "title": title,
            "description": description,
            "input_format": input_format,
            "output_format": output_format,
            "samples": samples,
            "time_limit": time_limit,
            "memory_limit": memory_limit,
            "difficulty": None,  # Codeforces使用rating，需要额外API
            "tags": [],
            "hints": None,
            "author": None,
            "url": url,
            "extra": {
                "oj_type": "codeforces",
                "contest_id": self._split_problem_id(problem_id)[0]
            }
        }

