# -*- coding: utf-8 -*-
"""
统一配置服务单元测试

测试 ConfigService（原 ConfigSingleton 和 ConfigManager 已合并）
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest


class TestConfigService:
    """ConfigService 测试类"""
    
    def test_singleton_pattern(self):
        """测试单例模式 - 多次获取返回同一实例"""
        from services.unified_config import get_config_service
        
        service1 = get_config_service()
        service2 = get_config_service()
        
        # 应该是同一个实例
        assert service1 is service2
    
    def test_config_loading(self):
        """测试配置加载"""
        from services.unified_config import get_config
        
        config = get_config()
        
        # 应该有默认配置
        assert config is not None
    
    def test_config_has_required_fields(self):
        """测试配置包含必要字段"""
        from services.unified_config import get_config
        
        cfg = get_config()
        
        # 检查核心配置字段
        assert hasattr(cfg, 'max_workers')
        assert hasattr(cfg, 'oj_base_url')
        assert hasattr(cfg, 'deepseek_api_key')
        assert hasattr(cfg, 'openai_api_key')
    
    def test_config_default_values(self):
        """测试默认值"""
        from services.unified_config import get_config
        
        cfg = get_config()
        
        # 检查默认值
        assert cfg.max_workers > 0
        assert cfg.llm_max_concurrency > 0
        # default_oj_adapter 可能是 "shsoj" 或 "aicoders"，取决于配置
        assert cfg.default_oj_adapter in ["shsoj", "aicoders"]


class TestConfigManager:
    """ConfigManager 兼容层测试"""
    
    def test_compatibility_layer(self):
        """测试兼容层正常工作"""
        from services.unified_config import ConfigManager
        
        # ConfigManager 现在是兼容层，不需要路径参数
        cfg_mgr = ConfigManager()
        cfg_mgr.load_or_init()
        
        assert cfg_mgr.cfg is not None
        assert cfg_mgr.cfg.max_workers > 0
    
    def test_save_and_reload(self):
        """测试保存和重新加载"""
        from services.unified_config import ConfigManager, reload_config
        
        cfg_mgr = ConfigManager()
        cfg_mgr.load_or_init()
        
        original_workers = cfg_mgr.cfg.max_workers
        
        # 修改配置
        cfg_mgr.cfg.max_workers = 99
        cfg_mgr.save()
        
        # 重新加载
        new_cfg = reload_config()
        
        # 验证更改已保存
        assert new_cfg.max_workers == 99
        
        # 恢复原值
        cfg_mgr.cfg.max_workers = original_workers
        cfg_mgr.save()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
