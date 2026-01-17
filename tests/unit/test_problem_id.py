# -*- coding: utf-8 -*-
"""
ProblemIdResolver 单元测试

测试题目ID解析和规范化功能
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from services.problem_id import get_problem_id_resolver


class TestProblemIdResolver:
    """ProblemIdResolver 测试类"""
    
    def setup_method(self):
        """每个测试方法前初始化"""
        self.resolver = get_problem_id_resolver()
    
    # ============= 纯数字ID判断测试 =============
    
    def test_is_pure_numeric_with_digits(self):
        """测试纯数字判断 - 纯数字"""
        assert self.resolver.is_pure_numeric("1234") is True
        assert self.resolver.is_pure_numeric("5678") is True
    
    def test_is_pure_numeric_with_spaces(self):
        """测试纯数字判断 - 带空格"""
        assert self.resolver.is_pure_numeric("  1234  ") is True
    
    def test_is_pure_numeric_with_letters(self):
        """测试纯数字判断 - 包含字母"""
        assert self.resolver.is_pure_numeric("abc123") is False
        assert self.resolver.is_pure_numeric("P1001") is False
    
    def test_is_pure_numeric_empty(self):
        """测试纯数字判断 - 空字符串"""
        assert self.resolver.is_pure_numeric("") is False
    
    # ============= 适配器查找测试 =============
    
    def test_find_adapter_for_shsoj_url(self):
        """测试SHSOJ URL的适配器查找"""
        url = "https://oj.aicoders.cn/problem/1234"
        adapter, lookup_id = self.resolver.find_adapter(url)
        
        # 应该找到适配器
        assert adapter is not None
        assert adapter.name in ["aicoders", "shsoj"]
    
    def test_find_adapter_for_pure_numeric(self):
        """测试纯数字ID的适配器查找"""
        adapter, lookup_id = self.resolver.find_adapter("1234")
        
        # 纯数字会构造URL后查找
        assert "1234" in lookup_id
    
    # ============= 规范化测试 =============
    
    def test_canonicalize_url(self):
        """测试URL规范化"""
        url = "https://oj.aicoders.cn/problem/1234"
        canonical = self.resolver.canonicalize(url)
        
        assert canonical is not None
        assert "1234" in canonical
    
    def test_canonicalize_pure_id(self):
        """测试纯ID规范化"""
        canonical = self.resolver.canonicalize("5678")
        
        assert canonical is not None
        assert "5678" in canonical
    
    def test_canonicalize_luogu(self):
        """测试洛谷URL规范化"""
        url = "https://www.luogu.com.cn/problem/P1001"
        canonical = self.resolver.canonicalize(url)
        
        assert canonical is not None
        assert "P1001" in canonical or "1001" in canonical
    
    def test_canonicalize_codeforces(self):
        """测试Codeforces URL规范化"""
        url = "https://codeforces.com/problemset/problem/1234/A"
        canonical = self.resolver.canonicalize(url)
        
        assert canonical is not None
        # Codeforces ID可能包含数字和字母
    
    # ============= 工作区路径测试 =============
    
    def test_get_workspace_dir(self):
        """测试工作区目录生成"""
        workspace = self.resolver.get_workspace_dir("1234", user_id=1)
        
        assert workspace is not None
        assert "user_1" in str(workspace)
        assert "1234" in str(workspace)
    
    def test_get_workspace_dir_requires_user_id(self):
        """测试工作区目录需要user_id"""
        with pytest.raises(ValueError):
            self.resolver.get_workspace_dir("1234", user_id=None)
    
    # ============= 边界情况测试 =============
    
    def test_canonicalize_empty_string(self):
        """测试空字符串规范化"""
        canonical = self.resolver.canonicalize("")
        
        # 空字符串应返回原值
        assert canonical == ""
    
    def test_canonicalize_whitespace(self):
        """测试空白字符处理"""
        canonical = self.resolver.canonicalize("  1234  ")
        
        assert canonical is not None
        assert "1234" in canonical


class TestPlatformDetection:
    """平台检测测试"""
    
    def setup_method(self):
        self.resolver = get_problem_id_resolver()
    
    def test_detect_aicoders_by_domain(self):
        """通过域名检测Aicoders"""
        url = "https://oj.aicoders.cn/problem/123"
        adapter, _ = self.resolver.find_adapter(url)
        
        assert adapter is not None
        assert adapter.name == "aicoders"
    
    def test_detect_codeforces_by_domain(self):
        """通过域名检测Codeforces"""
        url = "https://codeforces.com/contest/1234/problem/A"
        adapter, _ = self.resolver.find_adapter(url)
        
        assert adapter is not None
        assert adapter.name == "codeforces"
    
    def test_detect_luogu_by_domain(self):
        """通过域名检测洛谷"""
        url = "https://www.luogu.com.cn/problem/P1001"
        adapter, _ = self.resolver.find_adapter(url)
        
        assert adapter is not None
        assert adapter.name == "luogu"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
