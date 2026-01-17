# -*- coding: utf-8 -*-
"""LLM任务配置"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class LLMTaskConfig:
    """单个任务的LLM配置"""
    provider: str          # deepseek/gemini/siliconflow/openai
    api_key: str
    api_url: str
    model: str
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 65536
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider,
            'api_key': self.api_key,
            'api_url': self.api_url,
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'max_tokens': self.max_tokens
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'LLMTaskConfig':
        return LLMTaskConfig(
            provider=data['provider'],
            api_key=data['api_key'],
            api_url=data['api_url'],
            model=data['model'],
            temperature=data.get('temperature', 0.7),
            top_p=data.get('top_p', 0.9),
            max_tokens=data.get('max_tokens', 65536)
        )


class LLMConfigManager:
    """LLM配置管理器（支持每个功能独立配置）"""
    
    def __init__(self):
        self.configs: Dict[str, LLMTaskConfig] = {}
    
    def get_config(self, task: str) -> LLMTaskConfig:
        """获取指定任务的LLM配置"""
        if task not in self.configs:
            raise KeyError(f"任务 {task} 的LLM配置不存在")
        return self.configs[task]
    
    def set_config(self, task: str, config: LLMTaskConfig):
        """设置任务的LLM配置"""
        self.configs[task] = config
    
    def load_from_app_config(self, app_config):
        """从AppConfig加载（兼容现有配置）"""
        # OCR配置
        ocr_provider = getattr(app_config, 'llm_provider_ocr', 'siliconflow')
        self.configs['ocr'] = LLMTaskConfig(
            provider=ocr_provider,
            api_key=self._get_api_key(app_config, ocr_provider),
            api_url=self._get_api_url(app_config, ocr_provider),
            model=self._get_model(app_config, ocr_provider, 'ocr'),
            temperature=getattr(app_config, 'temperature_ocr', 0.2),
            top_p=getattr(app_config, 'top_p_ocr', 0.8),
        )
        
        # 数据生成配置
        # NOTE: llm_provider_generation 已废弃，现在由用户在任务界面选择统一的 llm_provider
        # 保留此字段以兼容旧数据，task_service.py 会设置它为统一的 llm_provider
        gen_provider = getattr(app_config, 'llm_provider_generation', 'deepseek')
        self.configs['generation'] = LLMTaskConfig(
            provider=gen_provider,
            api_key=self._get_api_key(app_config, gen_provider),
            api_url=self._get_api_url(app_config, gen_provider),
            model=self._get_model(app_config, gen_provider, 'generation'),
            temperature=getattr(app_config, 'temperature_generation', 0.7),
            top_p=getattr(app_config, 'top_p_generation', 0.9),
        )
        
        # 代码求解配置
        # NOTE: llm_provider_solution 已废弃，现在由用户在任务界面选择统一的 llm_provider
        # 保留此字段以兼容旧数据，task_service.py 会设置它为统一的 llm_provider
        solve_provider = getattr(app_config, 'llm_provider_solution', 'deepseek')
        self.configs['solution'] = LLMTaskConfig(
            provider=solve_provider,
            api_key=self._get_api_key(app_config, solve_provider),
            api_url=self._get_api_url(app_config, solve_provider),
            model=self._get_model(app_config, solve_provider, 'solution'),
            temperature=getattr(app_config, 'temperature_solution', 0.7),
            top_p=getattr(app_config, 'top_p_solution', 0.9),
        )
        
        # 搜索总结配置
        summary_provider = getattr(app_config, 'llm_provider_summary', 'gemini')
        self.configs['summary'] = LLMTaskConfig(
            provider=summary_provider,
            api_key=self._get_api_key(app_config, summary_provider),
            api_url=self._get_api_url(app_config, summary_provider),
            model=self._get_model(app_config, summary_provider, 'summary'),
            temperature=getattr(app_config, 'temperature_summary', 0.3),
            top_p=getattr(app_config, 'top_p_summary', 0.9),
        )
    
    def _get_api_key(self, app_config, provider: str) -> str:
        if provider == 'deepseek':
            return getattr(app_config, 'deepseek_api_key', '')
        elif provider == 'gemini':
            return getattr(app_config, 'gemini_api_key', '')
        elif provider == 'siliconflow':
            return getattr(app_config, 'deepseek_api_key_siliconflow', '')
        return ''
    
    def _get_api_url(self, app_config, provider: str) -> str:
        if provider == 'deepseek':
            return getattr(app_config, 'deepseek_api_url', 'https://api.deepseek.com/v1')
        elif provider == 'gemini':
            return getattr(app_config, 'gemini_api_url', 'https://generativelanguage.googleapis.com/v1beta')
        elif provider == 'siliconflow':
            return getattr(app_config, 'siliconflow_api_url', 'https://api.siliconflow.cn/v1')
        return ''
    
    def _get_model(self, app_config, provider: str, task: str) -> str:
        model_attr = f"{provider}_model_{task}"
        return getattr(app_config, model_attr, '')

