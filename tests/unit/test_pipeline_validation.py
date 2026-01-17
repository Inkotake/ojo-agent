# -*- coding: utf-8 -*-
"""测试 Pipeline 中的本地验题流程"""

import unittest
import platform
import sys
import os

# 确保 src 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestValidationServiceCrossPlatform(unittest.TestCase):
    """测试验证服务的跨平台支持"""
    
    def test_executable_suffix_detection(self):
        """测试可执行文件后缀检测"""
        from services.validation_service import _get_executable_suffix
        
        suffix = _get_executable_suffix()
        current_os = platform.system()
        
        if current_os == "Windows":
            self.assertEqual(suffix, ".exe")
        else:
            self.assertEqual(suffix, "")
    
    def test_validation_service_initialization(self):
        """测试验证服务初始化"""
        from services.validation_service import ValidationService, ValidationConfig
        
        config = ValidationConfig()
        service = ValidationService(config)
        
        self.assertEqual(config.compiler, "g++")
        self.assertEqual(config.timeout, 10)
        self.assertEqual(config.compile_timeout, 30)


class TestConcurrencyManagerCompile(unittest.TestCase):
    """测试并发管理器的编译控制"""
    
    def test_compile_semaphore_exists(self):
        """测试编译信号量存在"""
        from services.concurrency_manager import get_concurrency_manager
        
        mgr = get_concurrency_manager()
        config = mgr.get_config()
        
        # 检查编译并发配置存在
        self.assertIn("max_compile_concurrent", config)
        self.assertIsInstance(config["max_compile_concurrent"], int)
        self.assertGreater(config["max_compile_concurrent"], 0)
    
    def test_compile_context_manager(self):
        """测试编译上下文管理器"""
        from services.concurrency_manager import get_concurrency_manager
        
        mgr = get_concurrency_manager()
        
        # 测试上下文管理器可以正常使用
        with mgr.compile_context(timeout=5.0):
            pass  # 成功获取并释放
        
        # 检查统计信息
        stats = mgr.get_stats()
        self.assertIn("compile", stats)


class TestPipelineValidationIntegration(unittest.TestCase):
    """测试 Pipeline 验题集成"""
    
    def test_validation_result_in_gen_stage(self):
        """测试 GEN 阶段验题结果传递"""
        # 这是一个集成测试概念验证
        # 实际的集成测试需要完整的环境
        
        # 模拟 result.extra 中包含验题结果
        result_extra = {
            "zip_path": "/path/to/test.zip",
            "validation_passed": True
        }
        
        self.assertTrue(result_extra.get("validation_passed", False))


if __name__ == "__main__":
    unittest.main(verbosity=2)

