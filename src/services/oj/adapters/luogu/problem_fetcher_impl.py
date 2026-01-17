# -*- coding: utf-8 -*-
"""洛谷题面获取实现"""
from typing import Dict, Any, Optional
import re
import requests
from bs4 import BeautifulSoup
from loguru import logger

from ...base.problem_fetcher import ProblemFetcher


class LuoguProblemFetcher(ProblemFetcher):
    """洛谷题面获取器"""
    
    def __init__(self):
        self.timeout = 30
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def supports_url(self, url: str) -> bool:
        return 'luogu.com' in url.lower()
    
    def parse_problem_id(self, input_str: str) -> Optional[str]:
        """从URL或ID字符串中解析题目ID
        
        支持格式:
        - URL: https://www.luogu.com.cn/problem/P1000
        - URL: https://www.luogu.com.cn/problem/B4071
        - ID: P1000, B4071, U123456
        """
        input_str = input_str.strip()
        
        # 从URL中提取（支持P、B、U等前缀）
        if match := re.search(r'/problem/([PBUT]\d+)', input_str, re.IGNORECASE):
            return match.group(1).upper()
        
        # 直接是ID格式（如 P1000, B4071）
        if re.match(r'^[PBUT]\d+$', input_str, re.IGNORECASE):
            return input_str.upper()
        
        return None
    
    def fetch_problem(self, problem_id: str) -> Dict[str, Any]:
        """获取题目信息
        
        Args:
            problem_id: 题目ID（如 P1000, B4071）
            
        Returns:
            标准格式的题目数据
        """
        url = f"https://www.luogu.com.cn/problem/{problem_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"获取洛谷题目失败: {e}")
        
        # 解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        return self._parse_problem_page(soup, problem_id, url)
    
    def _parse_problem_page(self, soup: BeautifulSoup, problem_id: str, url: str) -> Dict[str, Any]:
        """解析题目页面HTML"""
        
        # 提取标题（通常在h1标签中）
        title = ""
        title_elem = soup.find('h1')
        if title_elem:
            title = title_elem.get_text(strip=True)
        else:
            # 尝试其他可能的位置
            for tag in soup.find_all(['h1', 'h2'], class_=lambda x: x and ('title' in str(x).lower() or 'problem' in str(x).lower())):
                text = tag.get_text(strip=True)
                if text:
                    title = text
                    break
        
        # 提取题目描述、输入格式、输出格式
        description = ""
        input_format = ""
        output_format = ""
        samples = []
        hints = ""
        
        # 洛谷页面结构：内容通常在h2标题下的div中
        # 按h2标题分割各个部分
        h2_elements = soup.find_all('h2')
        
        for h2 in h2_elements:
            h2_text = h2.get_text(strip=True)
            next_sibling = h2.find_next_sibling()
            
            content = ""
            if next_sibling:
                # 获取该h2后面的内容，直到下一个h2
                content_parts = []
                current = next_sibling
                while current and current.name != 'h2':
                    if current.name in ['div', 'p', 'pre', 'code']:
                        text = current.get_text(separator='\n', strip=True)
                        if text:
                            content_parts.append(text)
                    elif current.string and current.string.strip():
                        content_parts.append(current.string.strip())
                    current = current.find_next_sibling()
                
                content = '\n'.join(content_parts)
            
            # 根据h2标题分配内容
            if '题目描述' in h2_text or '问题描述' in h2_text or '描述' in h2_text:
                description = content
            elif '输入格式' in h2_text or '输入' in h2_text:
                input_format = content
            elif '输出格式' in h2_text or '输出' in h2_text:
                output_format = content
            elif '说明' in h2_text or '提示' in h2_text or '样例解释' in h2_text:
                hints = content if not hints else hints + '\n\n' + content
        
        # 如果描述为空，尝试从整个页面提取
        if not description:
            # 查找可能的内容区域
            content_areas = []
            for elem in soup.find_all(['article', 'main', 'div'], class_=lambda x: x and ('content' in str(x).lower() or 'problem' in str(x).lower())):
                text = elem.get_text(separator='\n', strip=True)
                if len(text) > 200:
                    content_areas.append(text)
            
            if content_areas:
                # 使用最长的内容作为描述
                description = max(content_areas, key=len)
        
        # 提取样例：查找包含"样例"的h2，然后查找后续的pre或code标签
        sample_h2 = None
        for h2 in h2_elements:
            h2_text = h2.get_text(strip=True)
            if '样例' in h2_text or 'Sample' in h2_text:
                sample_h2 = h2
                break
        
        if sample_h2:
            # 查找样例区域中的所有pre和code标签
            current = sample_h2.find_next_sibling()
            sample_input = None
            sample_output = None
            
            while current and current.name != 'h2':
                # 查找包含"输入"或"Input"的元素后的pre/code
                if current.name in ['div', 'p']:
                    text = current.get_text(strip=True)
                    if '输入' in text or 'Input' in text:
                        # 查找下一个pre或code
                        next_code = current.find_next(['pre', 'code'])
                        if next_code:
                            sample_input = next_code.get_text(strip=True)
                    elif '输出' in text or 'Output' in text:
                        # 查找下一个pre或code
                        next_code = current.find_next(['pre', 'code'])
                        if next_code:
                            sample_output = next_code.get_text(strip=True)
                            if sample_input:
                                samples.append({'input': sample_input, 'output': sample_output})
                                sample_input = None
                                sample_output = None
                
                # 直接查找pre/code标签（成对出现）
                if current.name in ['pre', 'code']:
                    text = current.get_text(strip=True)
                    if text and len(text) < 500:  # 样例通常不会太长
                        if sample_input is None:
                            sample_input = text
                        elif sample_output is None:
                            sample_output = text
                            samples.append({'input': sample_input, 'output': sample_output})
                            sample_input = None
                            sample_output = None
                
                current = current.find_next_sibling()
            
            # 如果最后还有未配对的输入
            if sample_input and sample_output is None:
                # 尝试查找下一个pre/code作为输出
                next_code = sample_h2.parent.find_next(['pre', 'code'])
                if next_code:
                    sample_output = next_code.get_text(strip=True)
                    samples.append({'input': sample_input, 'output': sample_output})
        
        # 备用方案：如果没有找到样例，查找所有pre/code标签，成对提取
        if not samples:
            code_blocks = soup.find_all(['pre', 'code'])
            # 成对提取（假设相邻的两个代码块是一个样例）
            for i in range(0, len(code_blocks) - 1, 2):
                if i + 1 < len(code_blocks):
                    inp = code_blocks[i].get_text(strip=True)
                    out = code_blocks[i + 1].get_text(strip=True)
                    if inp and out and len(inp) < 500 and len(out) < 500:
                        samples.append({'input': inp, 'output': out})
        
        # 提取时间限制和内存限制（如果页面中有）
        time_limit = None
        memory_limit = None
        page_text = soup.get_text()
        
        # 查找时间限制（可能以秒为单位）
        time_match = re.search(r'时间限制[：:]\s*([\d.]+)\s*(秒|s|ms)?', page_text, re.IGNORECASE)
        if time_match:
            time_value = float(time_match.group(1))
            unit = time_match.group(2) if time_match.group(2) else 's'
            if 'ms' in unit.lower():
                time_limit = int(time_value)
            else:
                time_limit = int(time_value * 1000)  # 转换为毫秒
        
        # 查找内存限制
        mem_match = re.search(r'内存限制[：:]\s*([\d.]+)\s*(MB|KB|GB|MiB)?', page_text, re.IGNORECASE)
        if mem_match:
            mem_value = float(mem_match.group(1))
            unit = mem_match.group(2) if mem_match.group(2) else 'MB'
            if 'KB' in unit.upper():
                memory_limit = int(mem_value / 1024)
            elif 'GB' in unit.upper() or 'GiB' in unit.upper():
                memory_limit = int(mem_value * 1024)
            else:
                memory_limit = int(mem_value)
        
        return {
            "id": problem_id,
            "title": title or f"洛谷 {problem_id}",
            "source": "luogu",
            "url": url,
            "description": description,
            "input_format": input_format,
            "output_format": output_format,
            "samples": samples if samples else [],
            "hints": hints,
            "time_limit": time_limit,
            "memory_limit": memory_limit,
            "tags": [],
            "difficulty": None,
            "extra": {}
        }

