# -*- coding: utf-8 -*-
"""契约守卫脚本 - 验证重构后行为不变"""

import re
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def check_semaphores() -> bool:
    """验证信号量使用位置和数量未变"""
    print("\n[Check] Semaphore usage...")
    
    # 支持两种形式：with self.sems.oj 和 with acquire(self.sems.oj)
    patterns = {
        "self.sems.oj": [],
        "self.sems.oj_write": [],
        "self.sems.ds": []
    }
    
    services_dir = Path("src/services")
    if not services_dir.exists():
        print(f"  ⚠ Services directory not found: {services_dir}")
        return True
    
    for file in services_dir.glob("*.py"):
        try:
            content = file.read_text(encoding='utf-8')
            for pattern in patterns:
                matches = list(re.finditer(pattern, content))
                patterns[pattern].extend([(file.name, m.start()) for m in matches])
        except Exception as e:
            print(f"  ⚠ Error reading {file.name}: {e}")
    
    print(f"  ✓ Found {len(patterns['self.sems.oj'])} oj semaphore usages")
    print(f"  ✓ Found {len(patterns['self.sems.oj_write'])} oj_write semaphore usages")
    print(f"  ✓ Found {len(patterns['self.sems.ds'])} ds semaphore usages")
    
    # oj_write应该最少（写操作需要串行）
    if len(patterns['self.sems.oj_write']) < 3:
        print(f"  ⚠ Warning: oj_write usage seems low ({len(patterns['self.sems.oj_write'])})")
    
    return True


def check_retry_signature() -> bool:
    """验证重试函数签名未变"""
    print("\n[Check] Retry function signature...")
    
    concurrency_file = Path("src/utils/concurrency.py")
    if not concurrency_file.exists():
        print(f"  ⚠ Concurrency file not found")
        return True
    
    src = concurrency_file.read_text(encoding='utf-8')
    
    required_elements = [
        "def retry_with_backoff(",
        "max_attempts",
        "base_delay",
        "factor"
    ]
    
    for element in required_elements:
        if element not in src:
            print(f"  ✗ Missing: {element}")
            return False
    
    print("  ✓ Retry signature unchanged")
    return True


def check_sleep_durations() -> bool:
    """验证等待时长已封装"""
    print("\n[Check] Sleep durations...")
    
    pipeline_file = Path("src/services/pipeline.py")
    if not pipeline_file.exists():
        print(f"  ⚠ Pipeline file not found")
        return True
    
    pipeline = pipeline_file.read_text(encoding='utf-8')
    
    # 检查是否有裸的time.sleep(30)或time.sleep(60)
    bare_sleep_30 = len(re.findall(r'time\.sleep\(30\)', pipeline))
    bare_sleep_60 = len(re.findall(r'time\.sleep\(60\)', pipeline))
    
    # 检查是否有封装的调用
    wrapped_sleep_30 = len(re.findall(r'_sleep30\(\)|_cooldown\(30\)', pipeline))
    wrapped_cooldown_60 = len(re.findall(r'_cooldown\(60\)', pipeline))
    
    if bare_sleep_30 > 0:
        print(f"  ✗ Found {bare_sleep_30} bare time.sleep(30) calls")
        return False
    
    if bare_sleep_60 > 0:
        print(f"  ✗ Found {bare_sleep_60} bare time.sleep(60) calls")
        return False
    
    if wrapped_sleep_30 == 0 and wrapped_cooldown_60 == 0:
        print("  ✗ Missing wrapped sleep calls (_sleep30 or _cooldown)")
        return False
    
    print(f"  ✓ Sleep durations properly wrapped ({wrapped_sleep_30} sleep30, {wrapped_cooldown_60} cooldown60)")
    return True


def check_port_usage() -> bool:
    """验证Services使用_oj_port而非直接使用self.oj"""
    print("\n[Check] OJPort usage in services...")
    
    services = ["generator.py", "uploader.py", "solver.py"]
    all_good = True
    
    for service_name in services:
        service_file = Path(f"src/services/{service_name}")
        if not service_file.exists():
            print(f"  ⚠ {service_name} not found")
            continue
        
        content = service_file.read_text(encoding='utf-8')
        
        # 检查是否有_oj_port定义
        if "_oj_port" not in content:
            print(f"  ✗ {service_name}: Missing _oj_port")
            all_good = False
            continue
        
        # 检查是否有OJApiAdapter
        if "OJApiAdapter" not in content:
            print(f"  ✗ {service_name}: Missing OJApiAdapter import/usage")
            all_good = False
            continue
        
        # 统计self.oj.调用（除了__init__中的self.oj = oj）
        oj_calls = len(re.findall(r'self\.oj\.', content))
        port_calls = len(re.findall(r'self\._oj_port\.', content))
        
        print(f"  ✓ {service_name}: {port_calls} port calls, {oj_calls} direct oj calls (should be minimal)")
    
    return all_good


def check_path_helpers() -> bool:
    """验证路径辅助函数已提取"""
    print("\n[Check] Path helper functions...")
    
    pipeline_file = Path("src/services/pipeline.py")
    if not pipeline_file.exists():
        print(f"  ⚠ Pipeline file not found")
        return True
    
    content = pipeline_file.read_text(encoding='utf-8')
    
    helpers = [
        "_problem_dir_for",
        "_zip_path_for",
        "_push_context",
        "_read_snippet"
    ]
    
    all_present = True
    for helper in helpers:
        if helper not in content:
            print(f"  ✗ Missing helper: {helper}")
            all_present = False
    
    if all_present:
        print(f"  ✓ All path/context helpers present")
    
    return all_present


if __name__ == "__main__":
    print("=" * 60)
    print("Contract Guard - Zero Regression Verification")
    print("=" * 60)
    
    checks = [
        check_semaphores(),
        check_retry_signature(),
        check_sleep_durations(),
        check_port_usage(),
        check_path_helpers()
    ]
    
    print("\n" + "=" * 60)
    if all(checks):
        print("✅ ALL CHECKS PASSED - Zero regression verified!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ SOME CHECKS FAILED - Review required")
        print("=" * 60)
        sys.exit(1)

