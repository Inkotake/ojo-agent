# -*- coding: utf-8 -*-
"""OJ API契约守卫测试 - 确保所有端点、Headers、参数未被修改"""

import inspect
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.oj_api import OJApi


def test_endpoints_unchanged():
    """验证所有OJ API端点未变"""
    src = inspect.getsource(OJApi)
    
    endpoints = [
        "/api/login",
        "//api/admin/problem/get-admin-problem-list",
        "//api/get-problem-detail?problemId=",
        "//api/file/upload-testcase-zip?mode=",
        "//api/admin/problem?pid=",
        "//api/admin/problem/get-problem-cases?pid=",
        "//api/admin/problem",  # PUT endpoint
        "//api/submit-problem-judge",
        "//api/get-submission-detail?submitId=",
    ]
    
    for endpoint in endpoints:
        assert endpoint in src, f"Endpoint changed or missing: {endpoint}"
    
    print("✓ All endpoints unchanged")


def test_headers_unchanged():
    """验证关键Headers存在且大小写不变"""
    src = inspect.getsource(OJApi)
    
    # 关键header键必须存在且大小写不变
    headers = ["authorization", "url-type", "Origin", "Referer"]
    for header in headers:
        assert header in src, f"Header missing or case changed: {header}"
    
    print("✓ All headers unchanged")


def test_timeout_proxy_verify_params():
    """验证超时/代理/证书参数传递不变"""
    src = inspect.getsource(OJApi)
    
    # 这些参数必须出现在requests调用中
    assert "timeout=self.timeout" in src or "timeout=timeout" in src
    assert "proxies=self.proxies" in src or "proxies=proxies" in src
    assert "verify=self.verify" in src or "verify=" in src
    
    print("✓ Timeout/proxies/verify params unchanged")


def test_http_methods_unchanged():
    """验证HTTP方法未变"""
    src = inspect.getsource(OJApi)
    
    # 确保POST/GET/PUT方法仍然存在
    assert ".post(" in src
    assert ".get(" in src
    assert ".put(" in src
    
    print("✓ HTTP methods unchanged")


if __name__ == "__main__":
    print("========== OJ API Contract Guard Tests ==========")
    try:
        test_endpoints_unchanged()
        test_headers_unchanged()
        test_timeout_proxy_verify_params()
        test_http_methods_unchanged()
        print("\n✅ All contract tests PASSED")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Contract test FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

