# -*- coding: utf-8 -*-
"""运行所有重构验证测试"""

import sys
import subprocess
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def run_test(script_name: str) -> bool:
    """运行单个测试脚本"""
    script_path = Path(__file__).parent / script_name
    print(f"\n{'='*60}")
    print(f"Running: {script_name}")
    print('='*60)
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=False,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False


def main():
    """运行所有测试"""
    print("🔍 Zero Regression Verification Suite")
    print("=" * 60)
    
    tests = [
        "contract_guard.py",
        "test_adapter_canary.py",
        "test_oj_api_contract.py"
    ]
    
    results = {}
    for test in tests:
        results[test] = run_test(test)
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    all_passed = True
    for test, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test:40} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("✅ All tests PASSED - Zero regression verified!")
        return 0
    else:
        print("❌ Some tests FAILED - Review required")
        return 1


if __name__ == "__main__":
    sys.exit(main())

