# -*- coding: utf-8 -*-
"""
LLM Provider 注册表 - 可扩展架构

所有 LLM Provider 的定义和配置都在此处管理。
添加新 Provider 只需在 PROVIDERS 中添加配置即可。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum


class ProviderCapability(Enum):
    """Provider 能力"""
    GENERATION = "generation"  # 数据生成
    SOLUTION = "solution"      # 代码求解
    OCR = "ocr"               # 图片识别
    SUMMARY = "summary"       # 文本摘要


@dataclass
class LLMProviderConfig:
    """LLM Provider 配置定义"""
    id: str                           # 唯一标识符
    name: str                         # 显示名称
    description: str                  # 描述
    
    # API 配置
    api_key_field: str                # AppConfig 中 API Key 字段名
    api_url_field: str                # AppConfig 中 API URL 字段名
    model_field: str                  # AppConfig 中模型字段名
    
    # 默认值
    default_api_url: str              # 默认 API URL
    default_model: str                # 默认模型名称
    
    # 能力
    capabilities: List[ProviderCapability] = field(default_factory=list)
    
    # 是否支持用户选择（用于生成+求解）
    user_selectable: bool = True
    
    # 额外配置字段（可选）
    extra_fields: Dict[str, Any] = field(default_factory=dict)


# ==================== Provider 定义 ====================

PROVIDERS: Dict[str, LLMProviderConfig] = {
    "deepseek": LLMProviderConfig(
        id="deepseek",
        name="DeepSeek",
        description="DeepSeek Reasoner - 推理能力强大",
        api_key_field="deepseek_api_key",
        api_url_field="deepseek_api_url",
        model_field="deepseek_model",
        default_api_url="https://api.deepseek.com/v1",
        default_model="deepseek-reasoner",
        capabilities=[
            ProviderCapability.GENERATION,
            ProviderCapability.SOLUTION,
            ProviderCapability.SUMMARY,
        ],
        user_selectable=True,
        extra_fields={
            "model_summary": "deepseek-chat",  # 摘要专用模型
        }
    ),
    
    "openai": LLMProviderConfig(
        id="openai",
        name="OpenAI 兼容",
        description="兼容 OpenAI API 格式的服务",
        api_key_field="openai_api_key",
        api_url_field="openai_api_url",
        model_field="openai_model",
        default_api_url="https://api.openai.com/v1",
        default_model="gpt-4",
        capabilities=[
            ProviderCapability.GENERATION,
            ProviderCapability.SOLUTION,
            ProviderCapability.SUMMARY,
        ],
        user_selectable=True,
    ),
    
    "siliconflow": LLMProviderConfig(
        id="siliconflow",
        name="硅基流动",
        description="硅基流动 - OCR 专用",
        api_key_field="deepseek_api_key_siliconflow",
        api_url_field="siliconflow_api_url",
        model_field="siliconflow_model_ocr",
        default_api_url="https://api.siliconflow.cn/v1",
        default_model="deepseek-ai/DeepSeek-OCR",
        capabilities=[
            ProviderCapability.OCR,
        ],
        user_selectable=False,  # 仅用于 OCR，不可选择
    ),
}


# ==================== Registry API ====================

def get_provider(provider_id: str) -> Optional[LLMProviderConfig]:
    """获取 Provider 配置"""
    return PROVIDERS.get(provider_id)


def get_all_providers() -> Dict[str, LLMProviderConfig]:
    """获取所有 Provider"""
    return PROVIDERS.copy()


def get_user_selectable_providers() -> List[LLMProviderConfig]:
    """获取用户可选择的 Provider（用于任务界面）"""
    return [p for p in PROVIDERS.values() if p.user_selectable]


def get_providers_by_capability(capability: ProviderCapability) -> List[LLMProviderConfig]:
    """根据能力获取 Provider 列表"""
    return [p for p in PROVIDERS.values() if capability in p.capabilities]


def get_provider_for_task(task: str) -> List[LLMProviderConfig]:
    """根据任务类型获取可用的 Provider 列表"""
    capability_map = {
        "generation": ProviderCapability.GENERATION,
        "solution": ProviderCapability.SOLUTION,
        "ocr": ProviderCapability.OCR,
        "summary": ProviderCapability.SUMMARY,
    }
    cap = capability_map.get(task)
    if cap:
        return get_providers_by_capability(cap)
    return list(PROVIDERS.values())


def provider_to_dict(provider: LLMProviderConfig) -> Dict[str, Any]:
    """将 Provider 配置转换为字典（用于 API 返回）"""
    return {
        "id": provider.id,
        "name": provider.name,
        "description": provider.description,
        "api_key_field": provider.api_key_field,
        "api_url_field": provider.api_url_field,
        "model_field": provider.model_field,
        "default_api_url": provider.default_api_url,
        "default_model": provider.default_model,
        "capabilities": [c.value for c in provider.capabilities],
        "user_selectable": provider.user_selectable,
    }


def get_all_providers_dict() -> List[Dict[str, Any]]:
    """获取所有 Provider 配置（字典格式）"""
    return [provider_to_dict(p) for p in PROVIDERS.values()]

