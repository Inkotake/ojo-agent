# -*- coding: utf-8 -*-
"""题解搜索服务：从OJ或网络搜索现有题解"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from loguru import logger

from services.oj_api import OJApi, OJAuth
from services.prompt_manager import get_prompt_manager

if TYPE_CHECKING:
    from services.llm.base import BaseLLMClient


class SolutionSearcher:
    """题解搜索器"""
    
    def __init__(self, oj_api: OJApi, workspace: Path, enable_search: bool = True, log_callback=None):
        """
        初始化题解搜索器
        
        Args:
            oj_api: OJ API客户端（保留参数以兼容）
            workspace: 工作目录
            enable_search: 是否启用题解搜索
            log_callback: 日志回调函数
        """
        self.oj_api = oj_api
        self.workspace = workspace
        self.enable_search = enable_search
        self.log_callback = log_callback or (lambda msg: None)
        self.cache_dir = workspace / ".solution_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _log(self, pid: str, msg: str):
        """记录日志"""
        self.log_callback(f"[{pid}] {msg}")
    
    def _cache_file(self, problem_id: str) -> Path:
        """缓存文件路径（内部辅助）"""
        return self.cache_dir / f"{problem_id}.json"
    
    def search_solutions(self, auth: OJAuth, problem_id: str, title: str = "", 
                        description: str = "", limit: int = 3, 
                        summary_llm: 'BaseLLMClient' = None) -> Optional[str]:
        """
        搜索题解
        
        Args:
            auth: OJ认证信息
            problem_id: 题目ID
            title: 题目标题（用于精准搜索）
            description: 题目描述（提取片段用于搜索）
            limit: 最多获取的题解数量
            summary_llm: 用于总结搜索结果的LLM客户端（可选）
        
        Returns:
            格式化的题解文本，如果未找到或禁用搜索则返回None
        """
        if not self.enable_search:
            self._log(problem_id, "题解搜索已禁用")
            return None
        
        self._log(problem_id, "开始搜索现有题解...")
        
        # 检查缓存
        cached = self._load_from_cache(problem_id)
        if cached:
            self._log(problem_id, "✓ 使用缓存的题解")
            return cached
        
        # 从网络搜索（传递题目信息，提取更多描述）
        desc_snippet = description[:200] if description else ""
        solutions = self._search_from_web(problem_id, title, desc_snippet, limit)
        
        if not solutions:
            self._log(problem_id, "未找到现有题解")
            return None
        
        self._log(problem_id, f"✓ 找到 {len(solutions)} 条参考资源")
        
        # 将搜索结果写入日志
        self._write_solutions_to_log(problem_id, solutions)
        
        # 如果启用总结且有总结LLM，总结搜索结果
        if summary_llm and len(solutions) > 0:
            try:
                self._log(problem_id, "正在总结搜索结果...")
                summary = self._summarize_results(problem_id, title, solutions, summary_llm)
                if summary:
                    self._log(problem_id, "✓ 搜索结果已总结")
                    # 将总结写入日志
                    self._write_summary_to_log(problem_id, summary)
                    # 返回总结后的内容
                    formatted = self._build_summary_context(summary)
                else:
                    # 总结失败，使用原始格式化
                    formatted = self._format_solutions(solutions, problem_id)
            except Exception as e:
                self._log(problem_id, f"总结搜索结果失败: {e}")
                # 总结失败，使用原始格式化
                formatted = self._format_solutions(solutions, problem_id)
        else:
            # 不总结，直接格式化
            formatted = self._format_solutions(solutions, problem_id)
        
        # 保存到缓存
        self._save_to_cache(problem_id, formatted)
        
        return formatted
    
    def _search_from_web(self, problem_id: str, title: str, description_snippet: str, limit: int) -> List[Dict[str, Any]]:
        """从网络搜索题解
        
        NOTE: 联网搜索功能暂时禁用 (2024-12-25)
        - 原因: 功能暂不需要使用，跳过此环节
        - 恢复: 删除下面的 return [] 即可重新启用
        """
        # === 联网搜索暂时禁用 ===
        self._log(problem_id, "联网搜索功能已禁用，跳过此环节")
        return []
        # === 禁用结束 ===
        
        # 以下是原始实现代码（保留备用）
        # try:
        #     self._log(problem_id, "正在网络搜索题解...")
        #     
        #     from services.search_engine import SearchEngine
        #     engine = SearchEngine()
        #     
        #     # 提取更多题面关键词（最多100字）
        #     desc_keywords = description_snippet[:100] if description_snippet else ""
        #     
        #     # 搜索题解（传递题目信息）
        #     search_results = engine.search_acm_solution(
        #         problem_id, 
        #         title=title,
        #         description_snippet=desc_keywords,
        #         max_results=limit
        #     )
        #     
        #     if not search_results:
        #         self._log(problem_id, "网络搜索未找到结果")
        #         return []
        #     
        #     self._log(problem_id, f"网络搜索找到 {len(search_results)} 条结果")
        #     
        #     # 格式化为统一结构，并限制snippet长度，过滤图片
        #     formatted_results = []
        #     for result in search_results:
        #         snippet = result.get("snippet", "")
        #         
        #         # 过滤图片相关内容
        #         import re
        #         snippet = re.sub(r'\[image[^\]]*\]|\!\[.*?\]\(.*?\)', '', snippet)
        #         snippet = re.sub(r'https?://[^\s]*\.(jpg|jpeg|png|gif|webp)', '', snippet, flags=re.IGNORECASE)
        #         
        #         # 限制每条snippet最多500字符，避免prompt过长
        #         if len(snippet) > 500:
        #             snippet = snippet[:500] + "..."
        #         
        #         if snippet.strip():  # 只添加有内容的结果
        #             formatted_results.append({
        #                 "source": "web",
        #                 "title": result.get("title", ""),
        #                 "url": result.get("url", ""),
        #                 "snippet": snippet.strip(),
        #                 "language": "未知"
        #             })
        #     
        #     return formatted_results
        # 
        # except Exception as e:
        #     self._log(problem_id, f"网络搜索失败: {e}")
        #     logger.warning(f"[{problem_id}] 网络搜索题解失败: {e}")
        #     return []
    
    def _format_solutions(self, solutions: List[Dict[str, Any]], problem_id: str) -> str:
        """格式化题解为提示词附加内容（简洁版，不影响模型发挥）"""
        if not solutions:
            return get_prompt_manager().get_no_solution_found_text()
        
        pm = get_prompt_manager()
        context_prefix = pm.get_search_context_prefix()
        
        formatted_parts = [context_prefix]
        
        for idx, sol in enumerate(solutions, 1):
            # 简洁格式，只保留标题、链接和关键摘要
            if sol.get("title"):
                title = sol['title']
                # 限制标题长度
                if len(title) > 100:
                    title = title[:100] + "..."
                formatted_parts.append(f"{idx}. {title}")
            
            if sol.get("url"):
                formatted_parts.append(f"   链接: {sol['url']}")
            
            # 添加简短摘要（网络搜索结果）
            if sol.get("snippet"):
                # 提取关键信息，避免过长
                snippet = sol['snippet']
                # 如果摘要中有算法关键词，优先保留
                keywords = ["算法", "思路", "解法", "复杂度", "algorithm", "solution", "approach"]
                has_keywords = any(kw in snippet.lower() for kw in keywords)
                
                if has_keywords or len(snippet) <= 200:
                    formatted_parts.append(f"   摘要: {snippet}")
                else:
                    # 太长且无关键词，截断
                    formatted_parts.append(f"   摘要: {snippet[:200]}...")
            
            formatted_parts.append("")  # 空行分隔
        
        formatted_parts.append("**注意**: 以上仅供参考，理解思路后独立实现。\n")
        
        return "\n".join(formatted_parts)
    
    def _get_canonical_id(self, original_id: str) -> str:
        """获取规范化的题目ID（适配器名_解析后ID）"""
        try:
            from services.oj.registry import get_global_registry
            
            registry = get_global_registry()
            adapter = registry.find_adapter_by_url(original_id)
            
            if adapter:
                fetcher = adapter.get_problem_fetcher()
                if fetcher:
                    parsed_id = fetcher.parse_problem_id(original_id)
                    if parsed_id:
                        # 使用统一规范：适配器名_解析后ID
                        return f"{adapter.name}_{parsed_id}"
        except Exception as e:
            logger.debug(f"[{original_id}] 解析适配器ID失败，使用原始ID: {e}")
        
        # 如果无法解析，返回原始ID
        return original_id
    
    def _write_solutions_to_log(self, problem_id: str, solutions: List[Dict[str, Any]]):
        """将搜索到的题解写入problem.log"""
        try:
            from pathlib import Path
            from utils.text import sanitize_filename
            
            canonical_id = self._get_canonical_id(problem_id)
            safe_pid = sanitize_filename(canonical_id)
            pdir = self.workspace / f"problem_{safe_pid}"
            pdir.mkdir(parents=True, exist_ok=True)
            
            prob_log_file = pdir / "problem.log"
            
            with open(prob_log_file, "a", encoding="utf-8", errors="ignore") as f:
                f.write("\n========== 搜索到的参考资源 ==========\n")
                
                for idx, sol in enumerate(solutions, 1):
                    f.write(f"\n--- 参考资源 {idx} ---\n")
                    
                    # 写入标题
                    if sol.get("title"):
                        title = sol['title']
                        if len(title) > 100:
                            title = title[:100] + "..."
                        f.write(f"标题: {title}\n")
                    
                    # 写入链接
                    if sol.get("url"):
                        f.write(f"链接: {sol['url']}\n")
                    
                    # 写入摘要（优先文字和代码，过滤图片链接）
                    if sol.get("snippet"):
                        snippet = sol['snippet']
                        # 过滤图片相关内容
                        import re
                        snippet = re.sub(r'\[image[^\]]*\]|\!\[.*?\]\(.*?\)', '', snippet)
                        snippet = re.sub(r'https?://[^\s]*\.(jpg|jpeg|png|gif|webp)', '[图片]', snippet, flags=re.IGNORECASE)
                        
                        # 限制长度
                        if len(snippet) > 500:
                            snippet = snippet[:500] + "..."
                        
                        if snippet.strip():
                            f.write(f"摘要: {snippet}\n")
                
                f.write("\n========== 参考资源结束 ==========\n\n")
                
        except Exception as e:
            logger.debug(f"写入题解到日志失败: {e}")
    
    def _summarize_results(self, problem_id: str, problem_title: str, 
                          solutions: List[Dict[str, Any]], llm_client) -> str:
        """使用LLM总结搜索结果"""
        try:
            # 构建总结prompt
            summary_prompt = f"题目: {problem_title} (ID: {problem_id})\n\n"
            summary_prompt += f"以下是搜索到的{len(solutions)}条参考资源：\n\n"
            
            for idx, sol in enumerate(solutions, 1):
                summary_prompt += f"{idx}. {sol.get('title', '未知标题')}\n"
                snippet = sol.get('snippet', '')[:300]  # 每条最多300字
                if snippet:
                    summary_prompt += f"   {snippet}\n\n"
            
            summary_prompt += """
请从上述资源中提取关键信息，输出格式：

**算法思路**: （1-2句话概括核心算法）
**时间复杂度**: （如O(n)、O(nlogn)等）
**关键注意点**: （列出2-3个要点）

要求：简洁、准确、仅提取算法相关信息，忽略无关内容。如果资源无关或无效，请输出"无有效信息"。
"""
            
            # 调用LLM总结（非流式，快速返回）
            content, _ = llm_client.chat_completion(
                summary_prompt,
                stream=False,
                system_prompt="You are an algorithm expert. Extract key algorithmic insights concisely."
            )
            
            return content if content else ""
            
        except Exception as e:
            logger.error(f"总结搜索结果失败: {e}")
            return ""
    
    def _write_summary_to_log(self, problem_id: str, summary: str):
        """将总结写入problem.log"""
        try:
            from pathlib import Path
            from utils.text import sanitize_filename
            
            canonical_id = self._get_canonical_id(problem_id)
            safe_pid = sanitize_filename(canonical_id)
            pdir = self.workspace / f"problem_{safe_pid}"
            prob_log_file = pdir / "problem.log"
            
            with open(prob_log_file, "a", encoding="utf-8", errors="ignore") as f:
                f.write("\n========== 搜索结果总结 ==========\n")
                f.write(summary)
                f.write("\n========== 总结结束 ==========\n\n")
                
        except Exception as e:
            logger.debug(f"写入总结到日志失败: {e}")
    
    def _build_summary_context(self, summary: str) -> str:
        """基于总结构建上下文"""
        pm = get_prompt_manager()
        context_prefix = pm.get_search_context_prefix()
        
        return f"{context_prefix}\n{summary}\n\n**注意**: 以上仅供参考，理解思路后独立实现。\n"
    
    # 缓存过期时间（秒），默认7天
    CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
    
    def _load_from_cache(self, problem_id: str) -> Optional[str]:
        """从缓存加载题解（带过期检查）"""
        try:
            cache_file = self._cache_file(problem_id)
            if cache_file.exists():
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                
                # 检查缓存是否过期
                cached_at = data.get("cached_at", 0)
                import time
                if time.time() - cached_at > self.CACHE_TTL_SECONDS:
                    logger.debug(f"[{problem_id}] 缓存已过期，将重新搜索")
                    cache_file.unlink()  # 删除过期缓存
                    return None
                
                return data.get("formatted_solutions")
        except Exception as e:
            logger.debug(f"加载缓存失败: {e}")
        return None
    
    def _save_to_cache(self, problem_id: str, formatted: str):
        """保存题解到缓存（带时间戳）"""
        try:
            import time
            cache_file = self._cache_file(problem_id)
            data = {
                "problem_id": problem_id,
                "formatted_solutions": formatted,
                "cached_at": time.time()
            }
            cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.debug(f"[{problem_id}] 题解已缓存")
        except Exception as e:
            logger.debug(f"保存缓存失败: {e}")
    
    def clear_cache(self, problem_id: Optional[str] = None):
        """清除缓存"""
        try:
            if problem_id:
                cache_file = self._cache_file(problem_id)
                if cache_file.exists():
                    cache_file.unlink()
                    logger.info(f"已清除题目 {problem_id} 的题解缓存")
            else:
                import shutil
                if self.cache_dir.exists():
                    shutil.rmtree(self.cache_dir)
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("已清除所有题解缓存")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")

