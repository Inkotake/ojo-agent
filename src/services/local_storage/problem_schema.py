# -*- coding: utf-8 -*-
"""题目数据标准格式定义"""

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
import json


@dataclass
class TestCase:
    """测试用例"""
    input: str
    output: str


@dataclass
class ProblemMetadata:
    """题目元数据（标准格式）
    
    这是跨OJ平台的统一题目数据格式
    """
    id: str                                 # 原始ID
    source: str                             # 来源OJ (shsoj/codeforces/atcoder/luogu等)
    title: str                              # 题目标题
    description: str                        # 题目描述
    input_format: str                       # 输入格式说明
    output_format: str                      # 输出格式说明
    samples: List[TestCase] = field(default_factory=list)  # 样例
    time_limit: Optional[int] = None        # 时间限制(ms)
    memory_limit: Optional[int] = None      # 内存限制(MB)
    difficulty: Optional[str] = None        # 难度
    tags: List[str] = field(default_factory=list)  # 标签
    hints: Optional[str] = None             # 提示
    author: Optional[str] = None            # 作者
    url: Optional[str] = None               # 原始URL
    extra: Dict[str, Any] = field(default_factory=dict)  # 平台特定额外信息
    
    def to_json(self) -> str:
        """转换为JSON字符串
        
        Returns:
            JSON字符串
        """
        data = asdict(self)
        # 特殊处理TestCase列表
        data['samples'] = [{'input': tc.input, 'output': tc.output} for tc in self.samples]
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    @staticmethod
    def from_json(json_str: str) -> 'ProblemMetadata':
        """从JSON字符串创建
        
        Args:
            json_str: JSON字符串
            
        Returns:
            ProblemMetadata实例
        """
        data = json.loads(json_str)
        # 特殊处理TestCase列表
        if 'samples' in data and data['samples']:
            data['samples'] = [TestCase(**tc) if isinstance(tc, dict) else tc for tc in data['samples']]
        # 确保tags和extra存在
        if 'tags' not in data or data['tags'] is None:
            data['tags'] = []
        if 'extra' not in data or data['extra'] is None:
            data['extra'] = {}
        return ProblemMetadata(**data)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ProblemMetadata':
        """从字典创建
        
        Args:
            data: 数据字典
            
        Returns:
            ProblemMetadata实例
        """
        # 处理samples
        if 'samples' in data and data['samples']:
            samples = []
            for tc in data['samples']:
                if isinstance(tc, TestCase):
                    samples.append(tc)
                elif isinstance(tc, dict):
                    samples.append(TestCase(**tc))
            data['samples'] = samples
        
        # 确保必需字段存在
        required_fields = ['id', 'source', 'title', 'description', 'input_format', 'output_format']
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"缺少必需字段: {field_name}")
        
        # 确保可选字段有默认值
        if 'tags' not in data:
            data['tags'] = []
        if 'extra' not in data:
            data['extra'] = {}
        if 'samples' not in data:
            data['samples'] = []
            
        return ProblemMetadata(**data)

