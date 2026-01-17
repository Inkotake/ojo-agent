# -*- coding: utf-8 -*-
"""SHSOJ状态码定义和工具函数"""

# SHSOJ判题状态码映射
STATUS_NAMES = {
    0: "Accepted",
    1: "Wrong Answer",
    2: "Time Limit Exceeded",
    3: "Memory Limit Exceeded",
    4: "Runtime Error",
    5: "Judging",
    6: "Compile Error",
    7: "Partially Accepted",
    8: "System Error",
    -2: "Compile Error"
}


def get_status_name(code: int) -> str:
    """获取状态码对应的名称"""
    return STATUS_NAMES.get(code, f"Status {code}")


def is_accepted(code: int) -> bool:
    """判断是否AC"""
    return code == 0


def is_compile_error(code: int) -> bool:
    """判断是否编译错误"""
    return code in (6, -2)


def is_system_error(code: int) -> bool:
    """判断是否系统错误"""
    return code == 8


def is_partially_accepted(code: int) -> bool:
    """判断是否部分正确（PAC）"""
    return code == 7


def is_wrong_answer(code: int) -> bool:
    """判断是否答案错误"""
    return code == 1


def is_runtime_error(code: int) -> bool:
    """判断是否运行时错误"""
    return code == 4


def is_judging(code: int) -> bool:
    """判断是否正在判题中"""
    return code == 5


def is_final_status(code: int) -> bool:
    """判断是否是最终状态（非判题中）"""
    return code != 5


def requires_data_regeneration(code: int) -> bool:
    """判断是否需要重新生成数据（WA/RE/PAC）"""
    return code in (1, 4, 7)
