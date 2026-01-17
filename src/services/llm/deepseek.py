# -*- coding: utf-8 -*-
"""DeepSeek LLM客户端实现"""

from __future__ import annotations

import json
import time
from typing import Tuple, Optional, Callable

import requests
from loguru import logger

from .base import BaseLLMClient


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API客户端"""
    
    def __init__(self, api_key: str, timeout: int = 60, proxies: dict | None = None,
                 verify_ssl: bool = True, model: str = "deepseek-reasoner", 
                 base_url: str = "https://api.deepseek.com/v1", **kwargs):
        super().__init__(api_key, timeout, proxies, verify_ssl, model=model, **kwargs)
        self.base_url = base_url
        self.default_model = model
    
    def chat_completion(self, prompt: str, model: str = None, max_tokens: int = 65536,
                       temperature: float = 0.7, top_p: float = 0.9,
                       stream: bool = False, on_chunk: Optional[Callable] = None,
                       system_prompt: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """调用DeepSeek API"""
        model = model or self.default_model
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream
        }
        
        for attempt in range(1, 6):
            try:
                if stream and on_chunk:
                    return self._chat_completion_stream(headers, payload, attempt, on_chunk)
                else:
                    return self._chat_completion_normal(headers, payload, attempt)
            except requests.exceptions.RequestException as e:
                if attempt >= 5:
                    raise RuntimeError(f"DeepSeek 重试仍失败: {e}")
                delay = 2 ** attempt
                logger.warning(f"DeepSeek 请求失败，{delay}s 后重试（第 {attempt} 次）: {e}")
                time.sleep(delay)
        
        raise RuntimeError("DeepSeek 重试仍失败")
    
    def _chat_completion_normal(self, headers: dict, payload: dict, attempt: int) -> Tuple[str, Optional[str]]:
        """非流式调用"""
        r = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload,
                         timeout=self.timeout, proxies=self.proxies, verify=self.verify_ssl)
        
        if r.status_code == 429 or r.status_code >= 500:
            retry_after = r.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
            logger.warning(f"DeepSeek {r.status_code}，{delay}s 后重试（第 {attempt} 次）")
            time.sleep(delay)
            raise requests.exceptions.RequestException(f"Status {r.status_code}")
        
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]["message"]
        return choice.get("content", "") or "", choice.get("reasoning_content")
    
    def _chat_completion_stream(self, headers: dict, payload: dict, attempt: int,
                                on_chunk: Callable) -> Tuple[str, Optional[str]]:
        """流式调用"""
        r = None
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
                proxies=self.proxies,
                verify=self.verify_ssl,
                stream=True
            )
            
            if r.status_code == 429 or r.status_code >= 500:
                retry_after = r.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                logger.warning(f"DeepSeek {r.status_code}，{delay}s 后重试（第 {attempt} 次）")
                time.sleep(delay)
                raise requests.exceptions.RequestException(f"Status {r.status_code}")
            
            r.raise_for_status()
            
            full_content = ""
            full_reasoning = ""
            
            for line in r.iter_lines(decode_unicode=False, delimiter=b'\n'):
                if not line:
                    continue
                
                try:
                    line_str = line.decode('utf-8')
                except:
                    continue
                
                if not line_str.startswith("data: "):
                    continue
                
                data_str = line_str[6:].strip()
                if data_str == "[DONE]":
                    break
                
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices")
                    if not choices:
                        continue
                    
                    delta = choices[0].get("delta", {})
                    reasoning_chunk = delta.get("reasoning_content")
                    content_chunk = delta.get("content")
                    
                    if reasoning_chunk:
                        full_reasoning += reasoning_chunk
                    if content_chunk:
                        full_content += content_chunk
                    
                    if on_chunk and (reasoning_chunk or content_chunk):
                        try:
                            on_chunk(reasoning_chunk or "", content_chunk or "")
                        except Exception as e:
                            logger.debug(f"on_chunk回调错误: {e}")
                except:
                    continue
            
            # 如果content为空但reasoning有内容，尝试从reasoning提取代码
            if not full_content and full_reasoning:
                logger.warning("DeepSeek返回content为空，尝试从reasoning提取代码")
                import re
                code_blocks = re.findall(r'```(?:python|py|cpp|c\+\+)?\s*(.*?)```', full_reasoning, re.DOTALL | re.IGNORECASE)
                if code_blocks:
                    full_content = code_blocks[-1].strip()
                    logger.info(f"从reasoning提取到代码，长度: {len(full_content)}")
            
            return full_content, full_reasoning if full_reasoning else None
        
        except requests.exceptions.Timeout as e:
            logger.error(f"DeepSeek API 超时: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepSeek API 请求错误: {e}")
            raise
        except Exception as e:
            logger.error(f"流式请求错误: {e}")
            raise
        finally:
            if r is not None:
                try:
                    r.close()
                except Exception:
                    pass
    
    def supports_vision(self) -> bool:
        """DeepSeek reasoner模型不支持视觉"""
        return False
    
    def ocr_image(self, image_url: str, prompt: Optional[str] = None) -> str:
        """DeepSeek reasoner不支持OCR"""
        raise NotImplementedError("DeepSeek reasoner模型不支持OCR，请使用SiliconFlowClient")
    
    def get_model_name(self) -> str:
        return self.default_model

