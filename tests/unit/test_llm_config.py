# -*- coding: utf-8 -*-
"""
LLM 配置模块测试

测试 v9.2 改动：
1. Provider Registry 可扩展架构
2. OCR 客户端懒加载（未配置时不阻塞）
3. 移除 Gemini 支持
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestProviderRegistry(unittest.TestCase):
    """测试 Provider Registry"""
    
    def test_get_all_providers(self):
        """测试获取所有 Provider"""
        from services.llm.provider_registry import get_all_providers, PROVIDERS
        
        providers = get_all_providers()
        
        # 应该有 3 个 Provider: deepseek, openai, siliconflow
        self.assertEqual(len(providers), 3)
        self.assertIn('deepseek', providers)
        self.assertIn('openai', providers)
        self.assertIn('siliconflow', providers)
    
    def test_get_user_selectable_providers(self):
        """测试获取用户可选择的 Provider"""
        from services.llm.provider_registry import get_user_selectable_providers
        
        providers = get_user_selectable_providers()
        
        # 用户可选择: deepseek, openai（siliconflow 是 OCR 专用）
        self.assertEqual(len(providers), 2)
        provider_ids = [p.id for p in providers]
        self.assertIn('deepseek', provider_ids)
        self.assertIn('openai', provider_ids)
        self.assertNotIn('siliconflow', provider_ids)
    
    def test_provider_has_required_fields(self):
        """测试 Provider 配置包含必要字段"""
        from services.llm.provider_registry import get_provider
        
        deepseek = get_provider('deepseek')
        
        self.assertIsNotNone(deepseek)
        self.assertEqual(deepseek.id, 'deepseek')
        self.assertEqual(deepseek.api_key_field, 'deepseek_api_key')
        self.assertEqual(deepseek.api_url_field, 'deepseek_api_url')
        self.assertEqual(deepseek.model_field, 'deepseek_model')
        self.assertTrue(deepseek.user_selectable)
    
    def test_siliconflow_is_ocr_only(self):
        """测试硅基流动只用于 OCR"""
        from services.llm.provider_registry import get_provider, ProviderCapability
        
        siliconflow = get_provider('siliconflow')
        
        self.assertIsNotNone(siliconflow)
        self.assertFalse(siliconflow.user_selectable)
        self.assertIn(ProviderCapability.OCR, siliconflow.capabilities)
        self.assertNotIn(ProviderCapability.GENERATION, siliconflow.capabilities)
    
    def test_gemini_removed(self):
        """测试 Gemini 已移除"""
        from services.llm.provider_registry import get_provider, get_all_providers
        
        # 不应该有 Gemini
        gemini = get_provider('gemini')
        self.assertIsNone(gemini)
        
        all_providers = get_all_providers()
        self.assertNotIn('gemini', all_providers)


class TestLLMFactoryWithRegistry(unittest.TestCase):
    """测试 LLM Factory 与 Provider Registry 集成"""
    
    def test_create_deepseek_client(self):
        """测试创建 DeepSeek 客户端"""
        from services.llm.factory import LLMFactory
        
        mock_config = MagicMock()
        mock_config.deepseek_api_key = "test_key"
        mock_config.deepseek_api_url = "https://api.deepseek.com/v1"
        mock_config.deepseek_model = "deepseek-reasoner"
        mock_config.request_timeout_minutes = 5
        mock_config.proxy_enabled = False
        mock_config.verify_ssl = True
        
        factory = LLMFactory(mock_config)
        client = factory.create("deepseek", task_type="generation")
        
        self.assertIsNotNone(client)
        # provider name 返回小写 id
        self.assertEqual(client.get_provider_name().lower(), "deepseek")
    
    def test_create_openai_client(self):
        """测试创建 OpenAI 兼容客户端"""
        from services.llm.factory import LLMFactory
        
        mock_config = MagicMock()
        mock_config.openai_api_key = "test_key"
        mock_config.openai_api_url = "https://api.openai.com/v1"
        mock_config.openai_model = "gpt-4"
        mock_config.request_timeout_minutes = 5
        mock_config.proxy_enabled = False
        mock_config.verify_ssl = True
        mock_config.thinking_budget = 16384
        mock_config.max_output_tokens = 65536
        
        factory = LLMFactory(mock_config)
        client = factory.create("openai", task_type="solution")
        
        self.assertIsNotNone(client)
    
    def test_siliconflow_requires_api_key(self):
        """测试硅基流动需要 API Key"""
        from services.llm.factory import LLMFactory
        
        mock_config = MagicMock()
        mock_config.deepseek_api_key_siliconflow = ""  # 未配置
        mock_config.siliconflow_api_url = "https://api.siliconflow.cn/v1"
        mock_config.siliconflow_model_ocr = "deepseek-ai/DeepSeek-OCR"
        mock_config.request_timeout_minutes = 5
        mock_config.proxy_enabled = False
        mock_config.verify_ssl = True
        
        factory = LLMFactory(mock_config)
        
        with self.assertRaises(ValueError) as context:
            factory.create("siliconflow", task_type="ocr")
        
        self.assertIn("硅基流动API密钥未配置", str(context.exception))
    
    def test_unknown_provider_falls_back_to_deepseek(self):
        """测试未知 Provider 回退到 DeepSeek"""
        from services.llm.factory import LLMFactory
        
        mock_config = MagicMock()
        mock_config.deepseek_api_key = "test_key"
        mock_config.deepseek_api_url = "https://api.deepseek.com/v1"
        mock_config.deepseek_model = "deepseek-reasoner"
        mock_config.request_timeout_minutes = 5
        mock_config.proxy_enabled = False
        mock_config.verify_ssl = True
        
        factory = LLMFactory(mock_config)
        client = factory.create("unknown_provider", task_type="general")
        
        self.assertIsNotNone(client)
        # provider name 返回小写 id
        self.assertEqual(client.get_provider_name().lower(), "deepseek")


class TestOCRLazyLoading(unittest.TestCase):
    """测试 OCR 懒加载"""
    
    def test_ocr_client_creation_fails_without_key(self):
        """测试 OCR 未配置时抛出异常"""
        from services.llm.factory import LLMFactory
        from unittest.mock import MagicMock
        
        mock_config = MagicMock()
        mock_config.deepseek_api_key_siliconflow = ""  # 未配置
        mock_config.siliconflow_api_url = "https://api.siliconflow.cn/v1"
        mock_config.siliconflow_model_ocr = "deepseek-ai/DeepSeek-OCR"
        mock_config.request_timeout_minutes = 5
        mock_config.proxy_enabled = False
        mock_config.verify_ssl = True
        
        factory = LLMFactory(mock_config)
        
        # OCR 未配置时应该抛出异常
        with self.assertRaises(ValueError):
            factory.create("siliconflow", task_type="ocr")
    
    def test_generator_works_without_ocr(self):
        """测试生成器在没有 OCR 时仍能工作"""
        from services.generator import GeneratorService
        
        mock_llm_client = MagicMock()
        mock_llm_client.get_provider_name.return_value = "DeepSeek"
        
        # OCR 客户端为 None
        generator = GeneratorService(
            oj=None,
            llm_client=mock_llm_client,
            ocr_client=None,  # 无 OCR
            workspace=Path("/tmp"),
            sems=None,
            log_callback=lambda msg: None
        )
        
        # 应该能成功创建
        self.assertIsNotNone(generator)
        self.assertIsNone(generator.ocr_client)


class TestTaskConfigLLMBinding(unittest.TestCase):
    """测试任务配置 LLM 绑定"""
    
    def test_task_config_has_llm_provider(self):
        """测试 TaskConfig 包含 llm_provider 字段"""
        from services.task_service import TaskConfig
        
        config = TaskConfig(llm_provider="openai")
        
        self.assertEqual(config.llm_provider, "openai")
    
    def test_task_config_default_llm_provider(self):
        """测试 TaskConfig 默认 LLM"""
        from services.task_service import TaskConfig
        
        config = TaskConfig()
        
        # 默认应该是 "deepseek"（系统默认值）
        self.assertEqual(config.llm_provider, "deepseek")


class TestAppConfigSimplified(unittest.TestCase):
    """测试简化后的 AppConfig"""
    
    def test_gemini_fields_removed(self):
        """测试 Gemini 字段已移除"""
        from services.unified_config import AppConfig
        
        config = AppConfig()
        
        # Gemini 字段应该不存在或为空
        self.assertFalse(hasattr(config, 'gemini_api_key') and config.gemini_api_key)
        self.assertFalse(hasattr(config, 'gemini_model') and config.gemini_model)
    
    def test_summary_default_to_deepseek(self):
        """测试摘要默认使用 DeepSeek"""
        from services.unified_config import AppConfig
        
        config = AppConfig()
        
        # Summary 应该默认使用 deepseek
        self.assertEqual(config.llm_provider_summary, "deepseek")


if __name__ == "__main__":
    unittest.main(verbosity=2)
