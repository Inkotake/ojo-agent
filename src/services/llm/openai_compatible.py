# -*- coding: utf-8 -*-
"""OpenAI兼容的LLM客户端（通过OpenAI SDK调用第三方接口）"""

from __future__ import annotations

from typing import Tuple, Optional, Callable

from loguru import logger

from .base import BaseLLMClient


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI兼容的API客户端（可用于Gemini等第三方接口）"""
    
    def __init__(self, api_key: str, timeout: int = 60, proxies: dict | None = None,
                 verify_ssl: bool = True, model: str = "gemini-2.5-pro", 
                 base_url: str = "https://hiapi.online/v1", **kwargs):
        super().__init__(api_key, timeout, proxies, verify_ssl, model=model, **kwargs)
        self.base_url = base_url
        self.default_model = model
        self._thinking_budget = kwargs.get("thinking_budget")
        self._max_output_tokens = kwargs.get("max_output_tokens")
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """初始化OpenAI客户端"""
        try:
            from openai import OpenAI
            
            # 创建客户端，指向第三方接口
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
            logger.info(f"OpenAI兼容客户端初始化成功: {self.base_url}")
        except ImportError:
            logger.error("未安装openai库，请运行: pip install openai")
            raise
        except Exception as e:
            logger.error(f"OpenAI客户端初始化失败: {e}")
            raise
    
    def chat_completion(self, prompt: str, model: str = None, max_tokens: int = 65536,
                       temperature: float = 0.7, top_p: float = 0.9,
                       stream: bool = False, on_chunk: Optional[Callable] = None,
                       system_prompt: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """调用OpenAI兼容的API"""
        model_name = model or self.default_model
        
        try:
            # 构建消息
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # 重试逻辑
            for attempt in range(1, 4):
                try:
                    if stream and on_chunk:
                        return self._generate_stream(messages, model_name, max_tokens, temperature, top_p, on_chunk)
                    else:
                        return self._generate_normal(messages, model_name, max_tokens, temperature, top_p)
                except Exception as e:
                    error_str = str(e).lower()
                    # 检查是否是速率限制错误
                    if "quota" in error_str or "rate" in error_str or "429" in error_str:
                        if attempt < 3:
                            import time
                            delay = 2 ** attempt
                            logger.warning(f"速率限制，{delay}s后重试（第{attempt}次）")
                            time.sleep(delay)
                            continue
                    raise
            
            raise RuntimeError("重试失败")
        
        except Exception as e:
            logger.error(f"OpenAI兼容API调用失败: {e}")
            raise
    
    def _generate_normal(self, messages, model: str, max_tokens: int, temperature: float, top_p: float) -> Tuple[str, Optional[str]]:
        """非流式生成"""
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=False
        )
        
        content = response.choices[0].message.content or ""
        return content, None
    
    def _generate_stream(self, messages, model: str, max_tokens: int, temperature: float, top_p: float, on_chunk: Callable) -> Tuple[str, Optional[str]]:
        """流式生成"""
        try:
            # 检查是否是Gemini 2.5模型，需要特殊配置
            extra_body = {}
            if "gemini-2.5" in model.lower() or "gemini-exp" in model.lower():
                # Gemini 2.5需要开启思考配置，并确保足够的输出长度
                # 思考预算和输出token分开计算，总预算 = thinking_budget + max_output_tokens
                thinking_budget = (
                    self._thinking_budget
                    if self._thinking_budget is not None
                    else self.extra_config.get("thinking_budget", 16384)
                )
                output_tokens = (
                    self._max_output_tokens
                    if self._max_output_tokens is not None
                    else self.extra_config.get("max_output_tokens", max_tokens or 65536)
                )
                extra_body = {
                    "google": {
                        "thinking_config": {
                            "include_thoughts": True,
                            "thinking_budget": thinking_budget
                        },
                        "max_output_tokens": output_tokens
                    }
                }
                logger.debug(f"Gemini 2.5模型，已启用思考配置（thinking_budget={thinking_budget}, max_output={output_tokens}）")
            
            # 发送流式请求
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stream=True,  # 核心：开启流式输出
                timeout=self.timeout,  # 确保超时时间足够长
                extra_body=extra_body if extra_body else None
            )
            
            full_content = ""
            full_reasoning = ""  # 思考摘要
            chunk_count = 0
            finish_reason = None
            system_prompt_filter = [
                "you are an expert", "competitive programming", "test case generator",
                "edge-case-rich", "validates algorithmic"
            ]
            
            # 迭代处理流式响应（逐块处理，持续读到结束）
            import time
            start_time = time.time()
            max_total_time = self.timeout * 2  # 总超时时间为配置的2倍（流式响应可能需要更长时间）
            last_chunk_time = time.time()
            max_chunk_interval = min(120, self.timeout)  # 每个chunk之间最大间隔（最多120秒）
            
            try:
                for chunk in response:
                    current_time = time.time()
                    
                    # 检查总超时（防止整个流式响应时间过长）
                    elapsed = current_time - start_time
                    if elapsed > max_total_time:
                        logger.warning(f"流式响应总超时：超过 {max_total_time} 秒（已等待 {elapsed:.1f} 秒），强制结束")
                        break
                    
                    # 检查chunk间隔超时（防止单个chunk等待时间过长）
                    chunk_interval = current_time - last_chunk_time
                    if chunk_interval > max_chunk_interval:
                        logger.warning(f"流式响应chunk超时：超过 {max_chunk_interval} 秒未收到新数据块（已等待 {chunk_interval:.1f} 秒），强制结束")
                        break
                    
                    last_chunk_time = current_time
                    chunk_count += 1
                    
                    # 调试：打印chunk结构
                    if chunk_count <= 3:
                        logger.debug(f"Chunk #{chunk_count}: {chunk}")
                    
                    # 检查是否有choices
                    if not chunk.choices:
                        continue
                    
                    choice = chunk.choices[0]
                    
                    # 检查finish_reason
                    if hasattr(choice, 'finish_reason') and choice.finish_reason:
                        finish_reason = choice.finish_reason
                        logger.debug(f"流式输出结束，finish_reason: {finish_reason}")
                        # 检查是否被过滤
                        if finish_reason in ['content_filter', 'safety']:
                            logger.warning(f"内容被安全拦截: {finish_reason}")
                        break
                    
                    # 提取delta
                    delta = choice.delta if hasattr(choice, 'delta') else None
                    if not delta:
                        continue
                    
                    # 提取内容
                    chunk_content = getattr(delta, 'content', None)
                    
                    # Filter out system prompt echoes (check throughout the stream)
                    if chunk_content:
                        content_lower = chunk_content.lower()
                        # Be aggressive in filtering system prompt patterns
                        if any(pattern in content_lower for pattern in system_prompt_filter):
                            logger.debug(f"过滤掉system prompt回显 (chunk {chunk_count}): {chunk_content[:100]}")
                            continue
                        # Also skip if this looks like a markdown fence followed immediately by prompt text
                        if chunk_content.strip() == '```' and chunk_count <= 3:
                            # Might be markdown wrapper around system prompt, peek ahead
                            continue
                    
                    # 提取思考（可能在不同字段中）
                    chunk_thought = None
                    # 尝试多种字段名
                    for thought_field in ['thought', 'thoughts', 'reasoning', 'think']:
                        if hasattr(delta, thought_field):
                            val = getattr(delta, thought_field)
                            if val:
                                chunk_thought = val
                                if chunk_count <= 3:
                                    logger.debug(f"找到思考字段: {thought_field} = {val[:100] if len(val) > 100 else val}")
                                break
                    
                    # 处理思考内容
                    if not chunk_thought:
                        # 兼容 OpenAI-兼容接口的 reasoning_content 字段
                        reasoning_content = getattr(delta, "reasoning_content", None)
                        if reasoning_content:
                            chunk_thought = reasoning_content
                    if chunk_thought:
                        full_reasoning += chunk_thought
                        if on_chunk:
                            try:
                                on_chunk(chunk_thought, "")  # 思考作为reasoning传递
                            except Exception as e:
                                logger.debug(f"on_chunk回调错误: {e}")
                    
                    # 处理正常内容
                    if chunk_content:  # 过滤空块（避免处理 None）
                        full_content += chunk_content
                        
                        # 调用回调函数
                        if on_chunk:
                            try:
                                on_chunk("", chunk_content)  # 内容作为content传递
                            except Exception as e:
                                logger.debug(f"on_chunk回调错误: {e}")
                
            except Exception as stream_error:
                logger.warning(f"流式读取中断: {stream_error}")
                # 继续处理已获取的内容
            finally:
                # 确保流式响应正确关闭，释放连接资源
                try:
                    if hasattr(response, 'close'):
                        response.close()
                except Exception as close_error:
                    logger.debug(f"关闭流式响应时出错（可忽略）: {close_error}")
            
            # Final cleanup: remove any system prompt that slipped through
            if full_content:
                lines = full_content.splitlines()
                cleaned_lines = []
                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    # Skip lines containing system prompt patterns (especially at the start)
                    if i < 10 and any(pattern in line_lower for pattern in system_prompt_filter):
                        logger.debug(f"最终清理：移除system prompt行: {line[:100]}")
                        continue
                    cleaned_lines.append(line)
                full_content = '\n'.join(cleaned_lines)
            
            logger.info(f"流式输出完成，共 {chunk_count} 个块，内容长度 {len(full_content)}，思考长度 {len(full_reasoning)}，finish_reason: {finish_reason}")
            
            # 检查是否被安全拦截且没有有效内容
            if finish_reason in ['content_filter', 'safety']:
                if not full_content and not full_reasoning:
                    error_msg = f"内容被安全策略拦截（{finish_reason}），且未返回任何有效内容。可能原因：1) 提示词包含敏感内容 2) API安全策略过于严格 3) 生成的代码触发了安全过滤"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                elif not full_content:
                    # 有 reasoning 但没有 content，记录警告但继续处理
                    logger.warning(f"内容被安全策略拦截（{finish_reason}），但保留了推理过程（{len(full_reasoning)}字符），将尝试从推理中提取代码")
            
            return full_content, full_reasoning if full_reasoning else None
        
        except Exception as e:
            logger.error(f"流式生成错误: {e}")
            raise
    
    def supports_vision(self) -> bool:
        """检查是否支持视觉（取决于模型）"""
        model_lower = self.default_model.lower()
        return "vision" in model_lower or "gpt-4" in model_lower or "gemini" in model_lower
    
    def ocr_image(self, image_url: str, prompt: Optional[str] = None) -> str:
        """OCR功能（如果模型支持vision）"""
        if not self.supports_vision():
            raise NotImplementedError(f"模型 {self.default_model} 不支持视觉功能")
        
        try:
            if prompt is None:
                from services.prompt_manager import get_prompt_manager
                pm = get_prompt_manager()
                prompt = pm.get_ocr_extraction_prompt()
            
            # 构建包含图片的消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            
            response = self._client.chat.completions.create(
                model=self.default_model,
                messages=messages,
                max_tokens=4096
            )
            
            return response.choices[0].message.content or ""
        
        except Exception as e:
            logger.error(f"OCR识别失败: {e}")
            return f"[OCR识别失败: {e}]"
    
    def get_model_name(self) -> str:
        return self.default_model

