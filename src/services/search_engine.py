# -*- coding: utf-8 -*-
"""搜索引擎：使用DuckDuckGo进行题解搜索"""

from __future__ import annotations

from typing import List, Dict
from loguru import logger


# 优先搜索的高质量算法站点
PRIORITY_SITES = [
    "site:codeforces.com/blog",
    "site:atcoder.jp",
    "site:luogu.com.cn/blog OR site:luogu.com.cn/problem",
    "site:blog.csdn.net/article",
    "site:cnblogs.com",
    "site:oi-wiki.org",
]

# 次要站点
SECONDARY_SITES = [
    "site:kattis.com",
    "site:poj.org",
    "site:acm.hdu.edu.cn",
    "site:onlinejudge.org OR site:uva.onlinejudge.org"
]


class SearchEngine:
    """搜索引擎（使用DuckDuckGo）"""
    
    def __init__(self):
        self._ddgs = None
    
    def _get_ddgs(self):
        """延迟初始化DDGS"""
        if self._ddgs is None:
            try:
                # 优先尝试新包名
                try:
                    from ddgs import DDGS
                except ImportError:
                    # 兼容旧包名
                    from duckduckgo_search import DDGS
                self._ddgs = DDGS
                logger.info("DuckDuckGo搜索引擎初始化成功")
            except ImportError:
                logger.error("未安装ddgs库，请运行: pip install ddgs")
                raise
        return self._ddgs
    
    def search_web(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """
        使用DuckDuckGo搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
        
        Returns:
            搜索结果列表 [{title, url, snippet}]
        """
        try:
            DDGS = self._get_ddgs()
            results = []
            
            with DDGS() as ddgs:
                # 尝试获取更详细的搜索结果
                for r in ddgs.text(
                    query, 
                    max_results=max_results, 
                    region="wt-wt",  # 改为全球搜索，获得更多结果
                    safesearch="off",  # 关闭安全搜索以获得更多技术内容
                    backend="auto"  # 自动选择最佳后端
                ):
                    # 提取更完整的snippet
                    snippet = r.get("body", "")
                    if not snippet or len(snippet) < 20:
                        # 如果snippet太短，尝试使用title作为补充
                        snippet = r.get("title", "") + " - " + snippet
                    
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": snippet
                    })
            
            return results
        
        except Exception as e:
            logger.error(f"DuckDuckGo搜索失败: {e}")
            return []
    
    def search_acm_solution(self, problem_id: str, title: str = "", 
                           description_snippet: str = "", oj_name: str = "",
                           max_results: int = 5) -> List[Dict[str, str]]:
        """
        专门搜索ACM题解
        
        Args:
            problem_id: 题目ID
            title: 题目标题（重要！）
            description_snippet: 题面描述片段（约20字，可选）
            oj_name: OJ平台名称（如"洛谷"、"Codeforces"）
            max_results: 最大结果数
        
        Returns:
            搜索结果列表 [{title, url, snippet}]
        """
        try:
            # 构建精准查询
            if oj_name:
                base_query = f"{oj_name} {problem_id}"
            else:
                base_query = problem_id
            
            # 添加题目标题（关键！）
            if title:
                # 限制标题长度避免查询过长
                title_short = title[:50] if len(title) > 50 else title
                base_query = f"{base_query} {title_short}"
            
            # 提取题面关键词（增加到50字，提高匹配度）
            desc_keywords = ""
            if description_snippet:
                desc_keywords = description_snippet[:50]
            
            # 添加强制关键词，过滤无关结果
            mandatory_keywords = "题解 OR solution OR editorial OR algorithm"
            
            # 生成多种检索词变体（增加题面描述的权重）
            variants = [
                f"{base_query} {desc_keywords} {mandatory_keywords}",  # 完整查询
                f'"{problem_id}" {title} 题解 算法',  # 精确匹配题号+标题
                f"{title} {desc_keywords} solution algorithm" if title else None,  # 英文查询
                f"{title} {desc_keywords} 算法 题解" if title else None,  # 中文查询
                f'"{problem_id}" 代码 解题思路',  # 备选查询
            ]
            variants = [v for v in variants if v]
            
            # 生成查询组合（优先高质量站点）
            queries = []
            
            # 第一轮：优先站点 + 强关键词
            for v in variants[:2]:  # 只用前2个变体
                for site in PRIORITY_SITES:
                    queries.append(f"{v} {site}")
            
            # 第二轮：通用搜索（带强关键词）
            for v in variants:
                queries.append(v)
            
            # 执行搜索并去重
            seen_urls = set()
            raw_results = []
            
            for q in queries:
                if len(raw_results) >= max_results * 3:  # 多搜索一些，后续过滤
                    break
                
                # 对每个查询搜索少量结果
                try:
                    for item in self.search_web(q, max_results=3):
                        url = item.get("url", "")
                        if not url or url in seen_urls:
                            continue
                        
                        seen_urls.add(url)
                        raw_results.append(item)
                        
                        if len(raw_results) >= max_results * 3:
                            break
                except Exception as e:
                    logger.debug(f"查询失败: {q}, 错误: {e}")
                    continue
            
            # 过滤相关性
            filtered_results = self._filter_relevant(raw_results, problem_id, title)
            
            # 取前N条
            results = filtered_results[:max_results]
            
            logger.info(f"搜索题解 {problem_id}: 原始{len(raw_results)}条，过滤后{len(filtered_results)}条，返回{len(results)}条")
            return results
        
        except Exception as e:
            logger.error(f"ACM题解搜索失败: {e}")
            return []
    
    def _filter_relevant(self, results: List[Dict[str, str]], problem_id: str, title: str) -> List[Dict[str, str]]:
        """过滤不相关的搜索结果"""
        filtered = []
        
        for r in results:
            # 检查标题、摘要和URL
            text = (r.get('title', '') + " " + r.get('snippet', '')).lower()
            url = r.get('url', '').lower()
            
            # 必须包含算法相关词汇或竞赛平台
            algo_keywords = [
                "算法", "solution", "editorial", "题解", "代码", "解题",
                "algorithm", "ac", "accepted", "复杂度", "思路",
                "approach", "解法", "题意", "分析", "codeforces", "leetcode",
                "luogu", "洛谷", "online judge", "oj", "competitive programming",
                "atcoder", "csdn", "cnblogs", "博客园"
            ]
            has_algo = any(kw in text or kw in url for kw in algo_keywords)
            
            # 过滤明显无关的内容（增加教材和课本检测）
            exclude_keywords = [
                "microsoft", "windows", "office", "下载软件", "激活",
                "download windows", "购买", "win10", "win11",
                "excel", "word", "powerpoint", "outlook",
                "系统安装", "驱动", "更新补丁",
                # 排除教材习题解答
                "textbook", "教材", "课本", "习题解答", "exercise solutions",
                "munkres", "rudin", "sipser", "topology", "analysis",
                "mathematical analysis", "theory of computation",
                "solutions manual", "instructor", "student solutions",
                "homework", "assignment", "教科书"
            ]
            has_exclude = any(kw in text or kw in url for kw in exclude_keywords)
            
            # 通过算法关键词检查且无排除词
            if has_algo and not has_exclude:
                filtered.append(r)
        
        return filtered

