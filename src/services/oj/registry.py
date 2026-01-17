# -*- coding: utf-8 -*-
"""适配器注册与发现系统"""

import re
from typing import Dict, List, Optional
from loguru import logger

from .base.adapter_base import OJAdapter
from .base.capabilities import OJCapability


class AdapterRegistry:
    """适配器注册表
    
    负责管理所有OJ适配器的注册、查找和能力发现
    """
    
    def __init__(self):
        self._adapters: Dict[str, OJAdapter] = {}
        self._url_patterns: Dict[str, str] = {}  # pattern -> adapter_name
    
    def register(self, adapter: OJAdapter):
        """注册适配器
        
        Args:
            adapter: OJ适配器实例
        """
        name = adapter.name
        if name in self._adapters:
            logger.warning(f"适配器 {name} 已存在，将被覆盖")
        
        self._adapters[name] = adapter
        logger.debug(f"注册适配器: {adapter.display_name} ({name}), 能力: {adapter.capabilities}")
    
    def get_adapter(self, name: str) -> Optional[OJAdapter]:
        """根据名称获取适配器
        
        Args:
            name: 适配器名称
            
        Returns:
            适配器实例，不存在返回None
        """
        return self._adapters.get(name)
    
    def list_adapters(self) -> List[OJAdapter]:
        """列出所有已注册的适配器
        
        Returns:
            适配器列表
        """
        return list(self._adapters.values())
    
    def find_adapter_by_url(self, url: str) -> Optional[OJAdapter]:
        """根据URL自动识别适配器
        
        Args:
            url: 题目URL
            
        Returns:
            匹配的适配器，未找到返回None
        """
        for adapter in self._adapters.values():
            fetcher = adapter.get_problem_fetcher()
            if fetcher and fetcher.supports_url(url):
                logger.debug(f"URL {url} 匹配到适配器: {adapter.name}")
                return adapter
        
        # 简单ID无法匹配适配器是正常情况，不需要记录日志
        return None
    
    def get_adapters_with_capability(self, capability: OJCapability) -> List[OJAdapter]:
        """获取支持指定能力的所有适配器
        
        Args:
            capability: 能力类型
            
        Returns:
            支持该能力的适配器列表
        """
        result = [a for a in self._adapters.values() if capability in a.capabilities]
        logger.debug(f"能力 {capability.name} 的适配器: {[a.name for a in result]}")
        return result
    
    def get_default_adapter(self, capability: OJCapability) -> Optional[OJAdapter]:
        """获取支持指定能力的默认适配器（第一个）
        
        Args:
            capability: 能力类型
            
        Returns:
            默认适配器，无可用适配器返回None
        """
        adapters = self.get_adapters_with_capability(capability)
        return adapters[0] if adapters else None


# 全局注册表实例
_global_registry = None


def get_global_registry() -> AdapterRegistry:
    """获取全局注册表实例（自动发现并注册所有适配器）
    
    Returns:
        全局注册表
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = AdapterRegistry()
        _auto_discover_and_register()
    return _global_registry


def _auto_discover_and_register():
    """自动发现并注册所有适配器（放文件即可用）
    
    支持两种模式：
    1. 文件系统扫描（开发环境）
    2. 显式导入（打包环境）
    """
    from pathlib import Path
    import importlib
    import sys
    
    # 已知的适配器列表（用于打包后的备用方案）
    # 格式: (module_name, adapter_class_name)
    known_adapters = [
        ('services.oj.adapters.shsoj', 'SHSOJAdapter'),  # SHSOJ 支持无参构造，会自动从配置加载
        ('services.oj.adapters.codeforces', 'CodeforcesAdapter'),
        ('services.oj.adapters.atcoder', 'AtCoderAdapter'),
        ('services.oj.adapters.luogu', 'LuoguAdapter'),
        ('services.oj.adapters.aicoders', 'AicodersAdapter'),
        ('services.oj.adapters.manual', 'ManualAdapter'),
        ('services.oj.adapters.hydrooj', 'HydroOJAdapter'),
    ]
    
    registered_count = 0
    
    def _try_register_adapter(module, adapter_class_name=None):
        """尝试从模块中注册适配器"""
        nonlocal registered_count
        found_any = False
        
        # 如果指定了类名，直接尝试
        if adapter_class_name:
            try:
                adapter_class = getattr(module, adapter_class_name, None)
                if adapter_class:
                    try:
                        adapter = adapter_class()
                        _global_registry.register(adapter)
                        logger.info(f"注册适配器: {adapter.display_name} ({adapter.name})")
                        registered_count += 1
                        found_any = True
                    except TypeError as e:
                        # 需要参数的适配器
                        logger.debug(f"适配器 {adapter_class_name} 需要手动注册（需要参数）: {e}")
                    except Exception as e:
                        # 记录详细错误信息，特别是对于 SHSOJ 适配器
                        error_msg = f"实例化适配器 {adapter_class_name} 失败: {type(e).__name__}: {e}"
                        if adapter_class_name == 'SHSOJAdapter':
                            logger.warning(error_msg)
                        else:
                            logger.debug(error_msg)
            except Exception as e:
                logger.debug(f"获取适配器类 {adapter_class_name} 失败: {e}")
        
        # 如果没有指定类名或指定类名失败，尝试自动查找
        if not found_any:
            for attr_name in dir(module):
                if attr_name.endswith('Adapter') and not attr_name.startswith('_'):
                    try:
                        adapter_class = getattr(module, attr_name)
                        # 检查是否是类且是 OJAdapter 的子类
                        if not isinstance(adapter_class, type):
                            continue
                        try:
                            adapter = adapter_class()
                            _global_registry.register(adapter)
                            logger.info(f"注册适配器: {adapter.display_name} ({adapter.name})")
                            registered_count += 1
                            found_any = True
                            break
                        except TypeError as e:
                            # 需要参数的适配器
                            logger.debug(f"适配器 {attr_name} 需要手动注册（需要参数）: {e}")
                        except Exception as e:
                            # 记录详细错误信息
                            error_msg = f"实例化适配器 {attr_name} 失败: {type(e).__name__}: {e}"
                            if attr_name == 'SHSOJAdapter':
                                logger.warning(error_msg)
                            else:
                                logger.debug(error_msg)
                    except Exception as e:
                        logger.debug(f"处理适配器属性 {attr_name} 失败: {e}")
        
        return found_any
    
    # 方法1：尝试文件系统扫描（开发环境）
    adapters_dir = Path(__file__).parent / "adapters"
    file_system_scan_success = False
    
    if adapters_dir.exists():
        try:
            for adapter_path in adapters_dir.iterdir():
                if not adapter_path.is_dir() or adapter_path.name.startswith('_'):
                    continue
                
                # 尝试导入适配器模块
                module_names = [
                    f"services.oj.adapters.{adapter_path.name}",
                    f"src.services.oj.adapters.{adapter_path.name}",
                ]
                
                # 尝试相对导入
                try:
                    current_file = Path(__file__)
                    if 'src' in str(current_file).replace('\\', '/'):
                        module_names.append(f".adapters.{adapter_path.name}")
                except:
                    pass
                
                module = None
                for module_name in module_names:
                    try:
                        if module_name.startswith('.'):
                            try:
                                module = importlib.import_module(module_name, package="services.oj")
                            except (ImportError, ValueError):
                                abs_name = module_name.lstrip('.')
                                if abs_name.startswith('adapters.'):
                                    abs_name = f"services.oj.{abs_name}"
                                module = importlib.import_module(abs_name)
                        else:
                            module = importlib.import_module(module_name)
                        break
                    except (ImportError, ModuleNotFoundError, ValueError):
                        continue
                
                if module:
                    if _try_register_adapter(module):
                        file_system_scan_success = True
        except Exception as e:
            logger.debug(f"文件系统扫描失败: {e}")
    
    # 方法2：如果文件系统扫描失败或没有找到适配器，使用显式导入（打包环境）
    if not file_system_scan_success or registered_count == 0:
        logger.debug("文件系统扫描未找到适配器或适配器数量为0，尝试显式导入...")
        for module_name, adapter_class_name in known_adapters:
            try:
                module = importlib.import_module(module_name)
                _try_register_adapter(module, adapter_class_name)
            except Exception as e:
                logger.debug(f"显式导入适配器 {module_name} 失败: {e}")
    
    # 最终检查
    final_count = len(_global_registry.list_adapters())
    if final_count > 0:
        logger.info(f"适配器注册完成，共注册 {final_count} 个适配器")
    else:
        logger.warning("未找到任何适配器，请检查适配器模块是否正确安装")

