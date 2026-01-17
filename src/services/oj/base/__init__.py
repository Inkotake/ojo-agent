# -*- coding: utf-8 -*-
"""OJ适配器基础接口定义"""

from .capabilities import OJCapability
from .adapter_base import OJAdapter
from .problem_fetcher import ProblemFetcher
from .data_uploader import DataUploader
from .solution_submitter import SolutionSubmitter
from .training_manager import TrainingManager
from .solution_provider import SolutionProvider

__all__ = [
    'OJCapability',
    'OJAdapter',
    'ProblemFetcher',
    'DataUploader',
    'SolutionSubmitter',
    'TrainingManager',
    'SolutionProvider',
]

