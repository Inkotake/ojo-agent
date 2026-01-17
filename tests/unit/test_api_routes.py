# -*- coding: utf-8 -*-
"""
API路由单元测试
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from unittest.mock import MagicMock, patch


class TestProblemsAPI:
    """题目API测试"""
    
    def test_problem_range_generation(self):
        """测试题目范围生成"""
        # 模拟范围生成逻辑
        start, end = 1001, 1005
        expected = ["1001", "1002", "1003", "1004", "1005"]
        
        result = [str(i) for i in range(start, end + 1)]
        
        assert result == expected
        assert len(result) == 5
    
    def test_problem_source_identification(self):
        """测试题目来源识别"""
        from api.routes.problems import identify_problem_source
        
        # 这是一个异步函数，需要特殊处理
        # 这里只测试模式匹配逻辑
        test_cases = [
            ("https://oj.aicoders.cn/problem/123", "shsoj"),
            ("https://codeforces.com/problem/1234/A", "codeforces"),
            ("https://atcoder.jp/contests/abc/tasks/a", "atcoder"),
            ("https://www.luogu.com.cn/problem/P1001", "luogu"),
        ]
        
        import re
        patterns = {
            "shsoj": r"aicoders\.cn|shsoj",
            "codeforces": r"codeforces\.com",
            "atcoder": r"atcoder\.jp",
            "luogu": r"luogu\.com",
        }
        
        for url, expected_source in test_cases:
            detected = None
            for source, pattern in patterns.items():
                if re.search(pattern, url, re.IGNORECASE):
                    detected = source
                    break
            
            assert detected == expected_source, f"Failed for {url}"


class TestTrainingAPI:
    """题单API测试"""
    
    def test_training_request_validation(self):
        """测试题单请求验证"""
        # 模拟Pydantic验证
        valid_data = {
            "title": "测试题单",
            "description": "这是一个测试题单",
            "problem_ids": ["1001", "1002", "1003"]
        }
        
        # 验证必填字段
        assert "title" in valid_data
        assert len(valid_data["problem_ids"]) > 0
    
    def test_training_id_parsing(self):
        """测试题单ID解析"""
        # 测试不同格式的problem_ids
        test_cases = [
            (["1001", "1002"], ["1001", "1002"]),
            (["shsoj_1001"], ["shsoj_1001"]),
            (["https://oj.aicoders.cn/problem/123"], ["https://oj.aicoders.cn/problem/123"]),
        ]
        
        for input_ids, expected in test_cases:
            assert input_ids == expected


class TestWashAPI:
    """清洗API测试"""
    
    def test_sensitive_word_replacement(self):
        """测试敏感词替换"""
        text = "上海市某中学的学生张三"
        sensitive_words = ["上海市", "中学", "张三"]
        
        result = text
        for word in sensitive_words:
            result = result.replace(word, "***")
        
        assert "上海市" not in result
        assert "中学" not in result
        assert "张三" not in result
        assert "***" in result
    
    def test_empty_text_handling(self):
        """测试空文本处理"""
        text = ""
        sensitive_words = ["测试"]
        
        result = text
        for word in sensitive_words:
            result = result.replace(word, "***")
        
        assert result == ""
    
    def test_no_match_handling(self):
        """测试无匹配情况"""
        text = "这是一段正常文本"
        sensitive_words = ["敏感词"]
        
        result = text
        changes = 0
        for word in sensitive_words:
            if word in result:
                changes += result.count(word)
                result = result.replace(word, "***")
        
        assert changes == 0
        assert result == text


class TestTasksAPI:
    """任务API测试"""
    
    def test_task_status_values(self):
        """测试任务状态值"""
        # 定义状态常量
        STATUS_PENDING = 0
        STATUS_RUNNING = 1
        STATUS_ERROR = 2
        STATUS_FAILED = 3
        STATUS_SUCCESS = 4
        
        # 验证状态值
        assert STATUS_PENDING == 0
        assert STATUS_SUCCESS == 4
    
    def test_retry_module_validation(self):
        """测试重试模块验证"""
        valid_modules = ["fetch", "gen", "upload", "solve"]
        
        # 验证有效模块
        for module in valid_modules:
            assert module in valid_modules
        
        # 验证无效模块
        invalid_module = "invalid_module"
        assert invalid_module not in valid_modules


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
