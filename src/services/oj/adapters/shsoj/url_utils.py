# -*- coding: utf-8 -*-
"""SHSOJ URL 工具函数（消除各模块中的重复代码）"""


def derive_api_url(frontend_url: str) -> str:
    """从前端URL推导API URL
    
    SHSOJ 平台的 URL 映射规则：
    - https://oj.shsbnu.net → https://oj-api.shsbnu.net
    - https://oj.aicoders.cn → https://api-tcoj.aicoders.cn
    
    Args:
        frontend_url: 前端URL或API URL
        
    Returns:
        API URL
    """
    url_lower = frontend_url.lower()
    
    # 如果已经是API地址，直接返回
    if 'api-tcoj.aicoders.cn' in url_lower:
        return "https://api-tcoj.aicoders.cn"
    if 'oj-api.shsbnu.net' in url_lower:
        return "https://oj-api.shsbnu.net"
    
    # 前端URL转换为API URL
    if 'oj.aicoders.cn' in url_lower or 'aicoders.cn/problem' in url_lower:
        return "https://api-tcoj.aicoders.cn"
    if 'oj.shsbnu.net' in url_lower or 'shsbnu.net' in url_lower:
        return "https://oj-api.shsbnu.net"
    
    # 默认使用原URL
    return frontend_url


def derive_frontend_url(base_url: str) -> str:
    """从 base_url 推导前端 URL（用于 Origin/Referer headers）
    
    Args:
        base_url: 基础URL（可能是前端或API URL）
        
    Returns:
        前端URL
    """
    return base_url.replace("oj-api.", "oj.").replace("api-tcoj.", "oj.")

