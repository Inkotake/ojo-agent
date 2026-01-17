# -*- coding: utf-8 -*-
"""Google Gemini LLM客户端实现"""

from __future__ import annotations

import time
from typing import Tuple, Optional, Callable

from loguru import logger

from .base import BaseLLMClient


class GeminiClient(BaseLLMClient):
    """Google Gemini API客户端"""
    
    def __init__(self, api_key: str, timeout: int = 60, proxies: dict | None = None,
                 verify_ssl: bool = True, model: str = "gemini-2.0-flash-exp", **kwargs):
        super().__init__(api_key, timeout, proxies, verify_ssl, model=model, **kwargs)
        self.default_model = model
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """初始化Gemini客户端"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai = genai
            logger.info("Gemini客户端初始化成功")
        except ImportError:
            logger.error("未安装google-generativeai库，请运行: pip install google-generativeai")
            raise
        except Exception as e:
            logger.error(f"Gemini客户端初始化失败: {e}")
            raise
    
    def chat_completion(self, prompt: str, model: str = None, max_tokens: int = 65536,
                       temperature: float = 0.7, top_p: float = 0.9,
                       stream: bool = False, on_chunk: Optional[Callable] = None,
                       system_prompt: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """调用Gemini API"""
        model_name = model or self.default_model
        
        try:
            # 配置生成参数
            generation_config = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
            }
            
            # 创建模型实例
            if system_prompt:
                model_instance = self._genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=generation_config,
                    system_instruction=system_prompt
                )
            else:
                model_instance = self._genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=generation_config
                )
            
            # 重试逻辑
            for attempt in range(1, 4):
                try:
                    if stream and on_chunk:
                        return self._generate_stream(model_instance, prompt, on_chunk)
                    else:
                        return self._generate_normal(model_instance, prompt)
                except Exception as e:
                    error_str = str(e).lower()
                    # 检查是否是速率限制错误
                    if "quota" in error_str or "rate" in error_str or "429" in error_str:
                        if attempt < 3:
                            delay = 2 ** attempt
                            logger.warning(f"Gemini速率限制，{delay}s后重试（第{attempt}次）")
                            time.sleep(delay)
                            continue
                    raise
            
            raise RuntimeError("Gemini重试失败")
        
        except Exception as e:
            logger.error(f"Gemini API调用失败: {e}")
            raise
    
    def _generate_normal(self, model_instance, prompt: str) -> Tuple[str, Optional[str]]:
        """非流式生成"""
        response = model_instance.generate_content(prompt)
        
        # 获取生成的文本
        if hasattr(response, 'text'):
            content = response.text
        elif hasattr(response, 'parts'):
            content = ''.join(part.text for part in response.parts if hasattr(part, 'text'))
        else:
            content = str(response)
        
        # Gemini不提供单独的推理过程，返回None
        return content, None
    
    def _generate_stream(self, model_instance, prompt: str, on_chunk: Callable) -> Tuple[str, Optional[str]]:
        """流式生成"""
        try:
            # 配置流式生成（Gemini 2.5需要启用思考配置）
            generation_config = {}
            
            # 检查是否是Gemini 2.5模型
            if "2.5" in self.default_model or "exp" in self.default_model:
                # 启用思考配置，增大token预算以避免输出截断
                try:
                    from google.genai import types
                    thinking_budget = 16384
                    output_tokens = 65536
                    generation_config = {
                        "thinking_config": types.ThinkingConfig(
                            include_thoughts=True,
                            thinking_budget=thinking_budget
                        ),
                        "max_output_tokens": output_tokens
                    }
                    logger.debug(f"Gemini 2.5模型，已启用思考配置（thinking_budget={thinking_budget}, max_output={output_tokens}）")
                except Exception as e:
                    logger.debug(f"配置思考失败: {e}，使用默认配置")
            
            response = model_instance.generate_content(prompt, stream=True, generation_config=generation_config)
            
            full_content = ""
            full_reasoning = ""  # 思考摘要
            chunk_count = 0
            
            # 迭代处理流式响应
            for chunk in response:
                chunk_count += 1
                
                # 从parts中提取内容和思考
                if hasattr(chunk, 'parts') and chunk.parts:
                    for part in chunk.parts:
                        # 检查是否是思考部分
                        is_thought = getattr(part, 'thought', False)
                        part_text = getattr(part, 'text', '')
                        
                        if part_text:
                            if is_thought:
                                # 思考摘要
                                full_reasoning += part_text
                                if on_chunk:
                                    try:
                                        on_chunk(part_text, "")  # 思考作为reasoning
                                    except Exception as e:
                                        logger.debug(f"on_chunk回调错误: {e}")
                            else:
                                # 正常内容
                                full_content += part_text
                                if on_chunk:
                                    try:
                                        on_chunk("", part_text)  # 内容作为content
                                    except Exception as e:
                                        logger.debug(f"on_chunk回调错误: {e}")
                else:
                    # 兼容旧版API，尝试直接获取text
                    try:
                        chunk_text = chunk.text if hasattr(chunk, 'text') else None
                        if chunk_text:
                            full_content += chunk_text
                            if on_chunk:
                                on_chunk("", chunk_text)
                    except (ValueError, AttributeError):
                        pass
            
            logger.debug(f"Gemini流式输出完成，共 {chunk_count} 个块，内容长度 {len(full_content)}，思考长度 {len(full_reasoning)}")
            return full_content, full_reasoning if full_reasoning else None
        
        except Exception as e:
            logger.error(f"Gemini流式生成错误: {e}")
            raise
    
    def supports_vision(self) -> bool:
        """Gemini支持视觉功能"""
        return "vision" in self.default_model.lower() or "pro" in self.default_model.lower() or "flash" in self.default_model.lower()
    
    def ocr_image(self, image_url: str, prompt: Optional[str] = None) -> str:
        """使用Gemini进行OCR"""
        try:
            if not self.supports_vision():
                raise NotImplementedError(f"模型 {self.default_model} 不支持视觉功能")
            
            # 默认OCR提示词
            if prompt is None:
                from services.prompt_manager import get_prompt_manager
                pm = get_prompt_manager()
                prompt = pm.get_ocr_extraction_prompt()
            
            # 创建模型实例
            model_instance = self._genai.GenerativeModel(model_name=self.default_model)
            
            # 处理图片
            if image_url.startswith("http://") or image_url.startswith("https://"):
                # 下载图片
                import requests
                r = requests.get(image_url, timeout=30, proxies=self.proxies, verify=self.verify_ssl)
                r.raise_for_status()
                
                # 使用PIL处理图片
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(r.content))
                
                # 生成内容
                response = model_instance.generate_content([prompt, img])
            elif image_url.startswith("data:"):
                # data URL格式
                import base64
                import io
                from PIL import Image
                
                # 解析data URL
                header, data = image_url.split(",", 1)
                img_data = base64.b64decode(data)
                img = Image.open(io.BytesIO(img_data))
                
                response = model_instance.generate_content([prompt, img])
            else:
                raise ValueError(f"不支持的图片URL格式: {image_url}")
            
            return response.text if hasattr(response, 'text') else str(response)
        
        except Exception as e:
            logger.error(f"Gemini OCR识别失败: {e}")
            return f"[OCR识别失败: {e}]"
    
    def get_model_name(self) -> str:
        return self.default_model

