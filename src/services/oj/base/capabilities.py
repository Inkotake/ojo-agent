# -*- coding: utf-8 -*-
"""OJ适配器能力枚举"""

from enum import Enum, auto


class OJCapability(Enum):
    """OJ适配器能力枚举"""
    FETCH_PROBLEM = auto()      # 拉取题面
    UPLOAD_DATA = auto()        # 上传测试数据
    SUBMIT_SOLUTION = auto()    # 提交解题
    MANAGE_TRAINING = auto()    # 题单管理
    JUDGE_STATUS = auto()       # 判题状态查询
    BATCH_FETCH = auto()        # 批量拉取
    PROVIDE_SOLUTION = auto()   # 提供官方题解（Editorial）

