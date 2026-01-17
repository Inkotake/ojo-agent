# -*- coding: utf-8 -*-
"""Adapter委托测试 - 验证OJApiAdapter是纯1:1直通"""

import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.oj_adapter import OJApiAdapter


class DummyOJApi:
    """模拟OJApi用于测试Adapter委托"""
    
    def __init__(self):
        self.calls = []
    
    def get_problem_detail(self, pid):
        self.calls.append(("get_problem_detail", pid))
        return {"id": pid, "title": "Test Problem"}
    
    def fetch_admin_problem(self, auth, pid):
        self.calls.append(("fetch_admin_problem", pid))
        return {"id": pid}
    
    def fetch_problem_cases(self, auth, pid):
        self.calls.append(("fetch_problem_cases", pid))
        return [{"input": "1", "output": "1"}]
    
    def get_submission_detail(self, auth, sid):
        self.calls.append(("get_submission_detail", sid))
        return {"id": sid, "status": 0}
    
    def resolve_actual_id(self, auth, pid):
        self.calls.append(("resolve_actual_id", pid))
        return (123, "123")
    
    def upload_testcase_zip(self, auth, zip_path, mode="default"):
        self.calls.append(("upload_testcase_zip", zip_path, mode))
        return {"fileListDir": "/tmp", "fileList": []}
    
    def put_admin_problem(self, auth, payload):
        self.calls.append(("put_admin_problem", len(payload)))
        return {"code": 0}
    
    def submit_problem_judge(self, auth, pid, code, language="C++"):
        self.calls.append(("submit_problem_judge", pid, language))
        return 12345


def test_adapter_is_pure_passthrough():
    """验证Adapter是纯直通，无额外逻辑"""
    api = DummyOJApi()
    adapter = OJApiAdapter(api)
    
    # Test read operations
    result1 = adapter.get_problem_detail("123")
    assert result1["id"] == "123"
    assert api.calls[-1] == ("get_problem_detail", "123")
    
    result2 = adapter.fetch_admin_problem(None, 456)
    assert result2["id"] == 456
    assert api.calls[-1] == ("fetch_admin_problem", 456)
    
    result3 = adapter.fetch_problem_cases(None, 789)
    assert len(result3) == 1
    assert api.calls[-1] == ("fetch_problem_cases", 789)
    
    result4 = adapter.get_submission_detail(None, 111)
    assert result4["status"] == 0
    assert api.calls[-1] == ("get_submission_detail", 111)
    
    result5 = adapter.resolve_actual_id(None, "222")
    assert result5 == (123, "123")
    assert api.calls[-1] == ("resolve_actual_id", "222")
    
    # Test write operations
    result6 = adapter.upload_testcase_zip(None, "/path/to/zip", "default")
    assert "fileListDir" in result6
    assert api.calls[-1] == ("upload_testcase_zip", "/path/to/zip", "default")
    
    result7 = adapter.put_admin_problem(None, {"key": "value"})
    assert result7["code"] == 0
    assert api.calls[-1] == ("put_admin_problem", 1)
    
    result8 = adapter.submit_problem_judge(None, "333", "code", "C++")
    assert result8 == 12345
    assert api.calls[-1] == ("submit_problem_judge", "333", "C++")
    
    print("✓ Adapter is pure 1:1 passthrough")


def test_adapter_preserves_call_order():
    """验证Adapter保持调用顺序"""
    api = DummyOJApi()
    adapter = OJApiAdapter(api)
    
    # 执行一系列操作
    adapter.get_problem_detail("A")
    adapter.resolve_actual_id(None, "B")
    adapter.upload_testcase_zip(None, "C", "default")
    
    # 验证调用顺序完全相同
    assert api.calls[0][0] == "get_problem_detail"
    assert api.calls[1][0] == "resolve_actual_id"
    assert api.calls[2][0] == "upload_testcase_zip"
    
    print("✓ Adapter preserves call order")


if __name__ == "__main__":
    print("========== Adapter Canary Tests ==========")
    try:
        test_adapter_is_pure_passthrough()
        test_adapter_preserves_call_order()
        print("\n✅ All adapter tests PASSED")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Adapter test FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

