# -*- coding: utf-8 -*-
"""OJ适配器模块 - 支持多OJ平台"""

from .ports import OJAdapter, ProblemFetcherPort, CaseUploaderPort, JudgeSubmitterPort

__all__ = [
    'OJAdapter',
    'ProblemFetcherPort', 
    'CaseUploaderPort',
    'JudgeSubmitterPort'
]

