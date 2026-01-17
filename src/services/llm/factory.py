# -*- coding: utf-8 -*-
"""
LLM工厂类：根据配置创建相应的LLM客户端

支持的 Provider:
- deepseek: DeepSeek Reasoner
- openai: OpenAI 兼容 API
- siliconflow: 硅基流动 (OCR 专用)

NOTE: Gemini 已移除，如需使用可通过 OpenAI 兼容模式
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from .base import BaseLLMClient
from .deepseek import DeepSeekClient
from .siliconflow import SiliconFlowClient
from .openai_compatible import OpenAICompatibleClient
from .task_config import LLMTaskConfig
from .provider_registry import get_provider, PROVIDERS

if TYPE_CHECKING:
    from services.unified_config import AppConfig


class LLMFactory:
    """LLM客户端工厂 - 基于 Provider Registry"""
    
    def __init__(self, config: AppConfig):
        self.config = config
    
    def create(self, provider: str, task_type: str = "general") -> BaseLLMClient:
        """
        创建LLM客户端
        
        Args:
            provider: 提供商名称 (deepseek, openai, siliconflow)
            task_type: 任务类型 (general, ocr, generation, solution, summary)
        
        Returns:
            LLM客户端实例
        """
        timeout_sec = self.config.request_timeout_minutes * 60
        proxies = self._get_proxies()
        verify_ssl = self.config.verify_ssl
        
        provider = provider.lower()
        
        if provider == "deepseek":
            return self._create_deepseek(timeout_sec, proxies, verify_ssl, task_type)
        elif provider == "siliconflow":
            return self._create_siliconflow(timeout_sec, proxies, verify_ssl, task_type)
        elif provider in ("openai", "openai_compatible"):
            return self._create_openai_compatible(timeout_sec, proxies, verify_ssl, task_type)
        else:
            logger.warning(f"未知的LLM提供商: {provider}，使用默认DeepSeek")
            return self._create_deepseek(timeout_sec, proxies, verify_ssl, task_type)
    
    def _create_deepseek(self, timeout: int, proxies: dict, verify_ssl: bool, task_type: str) -> DeepSeekClient:
        """创建DeepSeek客户端
        
        NOTE: 生成和求解现在统一使用 deepseek_model
        """
        api_key = self.config.deepseek_api_key
        base_url = getattr(self.config, "deepseek_api_url", "https://api.deepseek.com/v1")
        
        # 根据任务类型选择模型（生成和求解统一使用 deepseek_model）
        if task_type == "summary":
            model = getattr(self.config, "deepseek_model_summary", "deepseek-chat")
        else:
            # generation, solution, general 都使用统一的 deepseek_model
            model = getattr(self.config, "deepseek_model", "deepseek-reasoner")
        
        return DeepSeekClient(
            api_key=api_key,
            timeout=timeout,
            proxies=proxies,
            verify_ssl=verify_ssl,
            model=model,
            base_url=base_url
        )
    
    def _create_openai_compatible(self, timeout: int, proxies: dict, verify_ssl: bool, task_type: str) -> OpenAICompatibleClient:
        """创建OpenAI兼容客户端
        
        NOTE: 生成和求解现在统一使用 openai_model
        """
        api_key = getattr(self.config, "openai_api_key", "")
        base_url = getattr(self.config, "openai_api_url", "https://api.openai.com/v1")
        
        if not api_key:
            raise ValueError("OpenAI API密钥未配置")
        
        # 统一使用 openai_model
        model = getattr(self.config, "openai_model", "gpt-4")
        
        return OpenAICompatibleClient(
            api_key=api_key,
            timeout=timeout,
            proxies=proxies,
            verify_ssl=verify_ssl,
            model=model,
            base_url=base_url,
            thinking_budget=self.config.thinking_budget,
            max_output_tokens=self.config.max_output_tokens,
        )
    
    def _create_siliconflow(self, timeout: int, proxies: dict, verify_ssl: bool, task_type: str) -> SiliconFlowClient:
        """创建硅基流动客户端"""
        api_key = self.config.deepseek_api_key_siliconflow
        base_url = getattr(self.config, "siliconflow_api_url", "https://api.siliconflow.cn/v1")
        
        if not api_key:
            raise ValueError("硅基流动API密钥未配置")
        
        # OCR专用模型
        model = getattr(self.config, "siliconflow_model_ocr", "deepseek-ai/DeepSeek-OCR")
        
        return SiliconFlowClient(
            api_key=api_key,
            timeout=timeout,
            proxies=proxies,
            verify_ssl=verify_ssl,
            model=model,
            base_url=base_url
        )
    
    def _get_proxies(self) -> dict | None:
        """获取代理配置"""
        if not self.config.proxy_enabled:
            return None
        
        proxies = {}
        if self.config.http_proxy:
            proxies["http"] = self.config.http_proxy
        if self.config.https_proxy:
            proxies["https"] = self.config.https_proxy
        
        return proxies if proxies else None
    
    @staticmethod
    def create_from_task_config(config: LLMTaskConfig) -> BaseLLMClient:
        """从LLMTaskConfig创建客户端
        
        Args:
            config: 任务配置
            
        Returns:
            LLM客户端实例
            
        支持的 Provider: deepseek, openai, siliconflow
        """
        provider = config.provider
        
        if provider == "deepseek":
            return DeepSeekClient(
                api_key=config.api_key,
                base_url=config.api_url,
                model=config.model
            )
        elif provider == "siliconflow":
            return SiliconFlowClient(
                api_key=config.api_key,
                base_url=config.api_url,
                model=config.model
            )
        elif provider == "openai":
            return OpenAICompatibleClient(
                api_key=config.api_key,
                base_url=config.api_url,
                model=config.model,
                thinking_budget=getattr(config, "thinking_budget", None),
                max_output_tokens=getattr(config, "max_output_tokens", None),
            )
        else:
            raise ValueError(f"不支持的LLM provider: {provider}。支持: deepseek, openai, siliconflow")
    
    def create_for_task(self, task: str) -> BaseLLMClient:
        """
        根据任务类型创建合适的LLM客户端
        
        Args:
            task: 任务类型 (ocr, generation, solution, summary)
        
        Returns:
            LLM客户端实例
        
        NOTE: generation 和 solution 现在使用统一的 provider
        - task_service.py 会设置 llm_provider_generation 和 llm_provider_solution 为相同的值
        - 用户在任务界面选择一个 LLM，生成和求解统一使用该 LLM
        """
        if task == "ocr":
            provider = getattr(self.config, "llm_provider_ocr", "siliconflow")
            return self.create(provider, task_type="ocr")
        elif task == "generation":
            # NOTE: llm_provider_generation 已废弃，由用户在任务界面选择统一的 llm_provider
            provider = getattr(self.config, "llm_provider_generation", "deepseek")
            return self.create(provider, task_type="generation")
        elif task == "solution":
            # NOTE: llm_provider_solution 已废弃，由用户在任务界面选择统一的 llm_provider
            # task_service.py 会确保它与 llm_provider_generation 相同
            provider = getattr(self.config, "llm_provider_solution", "deepseek")
            return self.create(provider, task_type="solution")
        elif task == "summary":
            # 默认使用 deepseek 进行摘要（使用 deepseek-chat 模型）
            provider = getattr(self.config, "llm_provider_summary", "deepseek")
            return self.create(provider, task_type="summary")
        else:
            # 默认使用deepseek
            return self.create("deepseek", task_type="general")

