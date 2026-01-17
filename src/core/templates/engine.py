"""
模板引擎实现
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import re
from loguru import logger

from .types import Template, TemplateContext, TemplateType


class TemplateEngine:
    """
    模板引擎
    支持变量替换和条件渲染
    """
    
    def __init__(self):
        self._templates: Dict[str, Template] = {}
    
    def register_template(self, template: Template) -> None:
        """注册模板"""
        self._templates[template.name] = template
        logger.debug(f"注册模板: {template.name} ({template.type})")
    
    def load_from_file(self, template_file: Path) -> None:
        """从JSON文件加载模板"""
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for name, config in data.items():
                template = Template(
                    name=name,
                    type=TemplateType(config.get("type", "data_generation")),
                    content=config.get("content", ""),
                    variables=config.get("variables", []),
                    description=config.get("description", "")
                )
                self.register_template(template)
            
            logger.info(f"从文件加载 {len(data)} 个模板: {template_file}")
        except Exception as e:
            logger.error(f"加载模板文件失败: {e}")
    
    def render(self, template_name: str, context: TemplateContext) -> str:
        """
        渲染模板
        
        Args:
            template_name: 模板名称
            context: 渲染上下文
        
        Returns:
            渲染后的文本
        """
        template = self._templates.get(template_name)
        if not template:
            raise ValueError(f"模板不存在: {template_name}")
        
        # 验证必需变量
        if not template.validate(context.data):
            missing = [v for v in template.variables if v not in context.data]
            raise ValueError(f"缺少必需变量: {missing}")
        
        # 简单变量替换（支持 {variable} 和 {{variable}} 格式）
        result = template.content
        for key, value in context.data.items():
            # 替换 {key} 格式
            result = result.replace(f"{{{key}}}", str(value))
            # 替换 {{key}} 格式
            result = result.replace(f"{{{{{key}}}}}", str(value))
        
        return result
    
    def render_by_type(self, template_type: TemplateType, 
                       context: TemplateContext) -> str:
        """根据类型渲染模板（使用第一个匹配的模板）"""
        for template in self._templates.values():
            if template.type == template_type:
                return self.render(template.name, context)
        raise ValueError(f"未找到类型为 {template_type} 的模板")
    
    def list_templates(self, template_type: Optional[TemplateType] = None) -> List[Template]:
        """列出所有模板"""
        if template_type:
            return [t for t in self._templates.values() if t.type == template_type]
        return list(self._templates.values())
    
    def get_template(self, name: str) -> Optional[Template]:
        """获取模板"""
        return self._templates.get(name)


# 全局模板引擎实例
_global_template_engine: TemplateEngine = None


def get_template_engine() -> TemplateEngine:
    """获取全局模板引擎实例"""
    global _global_template_engine
    if _global_template_engine is None:
        _global_template_engine = TemplateEngine()
        
        # 自动加载模板
        try:
            template_file = Path("src/services/data/prompts.json")
            if template_file.exists():
                _global_template_engine.load_from_file(template_file)
        except Exception as e:
            logger.warning(f"自动加载模板失败: {e}")
    
    return _global_template_engine

