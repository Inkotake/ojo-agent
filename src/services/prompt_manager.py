# -*- coding: utf-8 -*-
"""Prompt管理器：统一加载和管理所有LLM提示词"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


class PromptManager:
    """提示词管理器，负责加载和提供所有prompt配置"""
    
    def __init__(self, prompts_file: Optional[Path] = None):
        if prompts_file is None:
            prompts_file = Path(__file__).parent / "data" / "prompts.json"
        
        self.prompts_file = prompts_file
        self.prompts: Dict[str, Any] = {}
        self._load_prompts()
    
    def _load_prompts(self):
        """加载prompts配置文件"""
        try:
            if not self.prompts_file.exists():
                logger.warning(f"Prompts文件不存在: {self.prompts_file}，使用空配置")
                self.prompts = {}
                return
            
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                self.prompts = json.load(f)
            
            logger.info(f"成功加载prompts配置: {self.prompts_file}")
        except Exception as e:
            logger.error(f"加载prompts配置失败: {e}")
            self.prompts = {}
    
    def reload(self):
        """重新加载配置（用于热更新）"""
        self._load_prompts()
    
    def get_data_generation_task_instructions(self, pid: str) -> str:
        """获取数据生成任务指令"""
        instructions = self.prompts.get("data_generation", {}).get("task_instructions", "")
        # 使用安全的替换方式，避免format()误解析花括号
        return instructions.replace("{pid}", pid)
    
    def get_data_generation_system_prompt(self) -> str:
        """获取数据生成系统提示"""
        return self.prompts.get("data_generation", {}).get("system_prompt", "")
    
    def get_solution_task_requirements(self) -> str:
        """获取解题任务要求"""
        return self.prompts.get("solution", {}).get("task_requirements", "")
    
    def get_solution_system_prompt(self) -> str:
        """获取解题系统提示"""
        return self.prompts.get("solution", {}).get("system_prompt", "")
    
    def get_ocr_extraction_prompt(self) -> str:
        """获取OCR提取提示"""
        return self.prompts.get("ocr", {}).get("extraction_prompt", "")
    
    def get_ocr_system_prompt(self) -> str:
        """获取OCR系统提示"""
        return self.prompts.get("ocr", {}).get("system_prompt", "")
    
    def get_search_query_template(self) -> str:
        """获取题解搜索查询模板"""
        return self.prompts.get("search_solution", {}).get("query_template", "")
    
    def get_search_context_prefix(self) -> str:
        """获取题解搜索上下文前缀"""
        return self.prompts.get("search_solution", {}).get("context_prefix", "")
    
    def get_no_solution_found_text(self) -> str:
        """获取未找到题解时的提示文本"""
        return self.prompts.get("search_solution", {}).get("no_solution_found", "")


# 全局单例
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """获取全局提示词管理器单例"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager

