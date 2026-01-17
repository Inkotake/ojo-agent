# -*- coding: utf-8 -*-
"""LLM客户端抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple, Optional, Callable


class BaseLLMClient(ABC):
    """LLM客户端抽象基类，定义统一接口"""
    
    def __init__(self, api_key: str, timeout: int = 60, proxies: dict | None = None, 
                 verify_ssl: bool = True, **kwargs):
        self.api_key = api_key
        self.timeout = timeout
        self.proxies = proxies or None
        self.verify_ssl = verify_ssl
        self.extra_config = kwargs
    
    @abstractmethod
    def chat_completion(self, prompt: str, model: str = None, max_tokens: int = 65536,
                       temperature: float = 0.7, top_p: float = 0.9,
                       stream: bool = False, on_chunk: Optional[Callable] = None,
                       system_prompt: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        调用LLM进行聊天补全
        
        Args:
            prompt: 用户提示词
            model: 模型名称（可选，使用默认模型）
            max_tokens: 最大token数
            stream: 是否使用流式模式
            on_chunk: 流式模式下的回调函数，接收 (reasoning_chunk, content_chunk)
            system_prompt: 系统提示词（可选）
        
        Returns:
            (完整内容, 完整推理过程)，如果模型不支持推理过程则返回None
        """
        pass
    
    @abstractmethod
    def supports_vision(self) -> bool:
        """检查模型是否支持视觉功能（图片识别）"""
        pass
    
    @abstractmethod
    def ocr_image(self, image_url: str, prompt: Optional[str] = None) -> str:
        """对图片进行OCR识别"""
        pass
    
    def get_model_name(self) -> str:
        """获取当前使用的模型名称"""
        return self.extra_config.get("model", "unknown")
    
    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return self.__class__.__name__.replace("Client", "").lower()

