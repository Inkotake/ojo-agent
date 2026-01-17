# -*- coding: utf-8 -*-
"""
TaskService 单元测试
"""

import unittest
import sys
from pathlib import Path
from dataclasses import dataclass

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestTaskConfig(unittest.TestCase):
    """TaskConfig 测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        from services.task_service import TaskConfig
        
        config = TaskConfig()
        
        self.assertTrue(config.enable_fetch)
        self.assertTrue(config.enable_generation)
        self.assertTrue(config.enable_upload)
        self.assertTrue(config.enable_solve)
        self.assertIsNone(config.source_adapter)
        self.assertIsNone(config.target_adapter)
    
    def test_default_llm_provider(self):
        """测试默认 LLM provider"""
        from services.task_service import TaskConfig
        
        config = TaskConfig()
        
        # 默认应该是 deepseek
        self.assertEqual(config.llm_provider, "deepseek")
    
    def test_custom_llm_provider(self):
        """测试自定义 LLM provider"""
        from services.task_service import TaskConfig
        
        config = TaskConfig(llm_provider="gemini")
        
        self.assertEqual(config.llm_provider, "gemini")
    
    def test_to_modules_dict(self):
        """测试转换为模块字典"""
        from services.task_service import TaskConfig
        
        config = TaskConfig(
            enable_fetch=True,
            enable_generation=False,
            enable_upload=True,
            enable_solve=False
        )
        
        modules = config.to_modules_dict()
        
        self.assertTrue(modules["fetch"])
        self.assertFalse(modules["gen"])
        self.assertTrue(modules["upload"])
        self.assertFalse(modules["solve"])
        self.assertFalse(modules["training"])
    
    def test_get_fetch_adapter_with_problem_adapters(self):
        """测试从 problem_adapters 获取拉取适配器"""
        from services.task_service import TaskConfig
        
        config = TaskConfig(
            problem_adapters={"P1001": "luogu", "P1002": "codeforces"}
        )
        
        self.assertEqual(config.get_fetch_adapter("P1001"), "luogu")
        self.assertEqual(config.get_fetch_adapter("P1002"), "codeforces")
        self.assertIsNone(config.get_fetch_adapter("P1003"))  # 不在映射中
    
    def test_get_fetch_adapter_fallback_to_source(self):
        """测试 fallback 到 source_adapter"""
        from services.task_service import TaskConfig
        
        config = TaskConfig(source_adapter="shsoj")
        
        self.assertEqual(config.get_fetch_adapter("P1001"), "shsoj")


class TestTaskResult(unittest.TestCase):
    """TaskResult 测试"""
    
    def test_success_result(self):
        """测试成功结果"""
        from services.task_service import TaskResult
        
        result = TaskResult(
            task_id=1,
            problem_id="P1000",
            success=True,
            status="success",
            uploaded_url="https://oj.example.com/problem/123"
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.uploaded_url)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.logs, [])
    
    def test_failed_result(self):
        """测试失败结果"""
        from services.task_service import TaskResult
        
        result = TaskResult(
            task_id=2,
            problem_id="P1001",
            success=False,
            status="failed",
            error_message="生成失败"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_message, "生成失败")


class TestTaskServiceSuccessDetection(unittest.TestCase):
    """测试成功判断逻辑"""
    
    def test_detect_success_from_pipeline_result(self):
        """测试从 Pipeline 结果检测成功"""
        from services.task_service import TaskConfig
        
        # 模拟 Pipeline 的 TaskResult
        @dataclass
        class MockPipelineResult:
            original_id: str
            ok_gen: bool = False
            ok_upload: bool = False
            ok_solve: bool = False
            extra: dict = None
            
            def __post_init__(self):
                if self.extra is None:
                    self.extra = {}
        
        result = MockPipelineResult(
            original_id="P1000",
            ok_gen=True,
            ok_upload=True,
            ok_solve=True
        )
        
        config = TaskConfig(
            enable_generation=True,
            enable_upload=True,
            enable_solve=True
        )
        
        # 检测逻辑
        module_success = []
        if config.enable_generation:
            module_success.append(result.ok_gen)
        if config.enable_upload:
            module_success.append(result.ok_upload)
        if config.enable_solve:
            module_success.append(result.ok_solve)
        
        success = all(module_success)
        self.assertTrue(success)
    
    def test_detect_failure_from_pipeline_result(self):
        """测试从 Pipeline 结果检测失败"""
        from services.task_service import TaskConfig
        
        @dataclass
        class MockPipelineResult:
            original_id: str
            ok_gen: bool = False
            ok_upload: bool = False
            ok_solve: bool = False
            extra: dict = None
        
        result = MockPipelineResult(
            original_id="P1000",
            ok_gen=False,
            ok_upload=False,
            ok_solve=False
        )
        
        config = TaskConfig(enable_generation=True)
        
        module_success = []
        if config.enable_generation:
            module_success.append(result.ok_gen)
        
        success = all(module_success) if module_success else True
        self.assertFalse(success)


class TestTaskServiceSingleton(unittest.TestCase):
    """测试 TaskService 单例"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from services.task_service import get_task_service
        
        service1 = get_task_service()
        service2 = get_task_service()
        
        self.assertIs(service1, service2)
    
    def test_has_executor(self):
        """测试线程池存在"""
        from services.task_service import get_task_service
        
        service = get_task_service()
        
        self.assertTrue(hasattr(service, '_executor'))
        self.assertIsNotNone(service._executor)


if __name__ == "__main__":
    unittest.main(verbosity=2)
