#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重置管理员密码脚本
用法: python scripts/reset-admin-password.py <username> <new_password>
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def reset_password(username: str, new_password: str):
    """重置用户密码"""
    try:
        from core.database import get_database
        from services.auth_service import get_auth_service
        
        db = get_database()
        auth_service = get_auth_service()
        
        # 查找用户
        user = db.get_user_by_username(username)
        if not user:
            print(f"错误: 用户 '{username}' 不存在")
            return False
        
        # 验证密码强度
        valid, msg = auth_service.validate_password_strength(new_password)
        if not valid:
            print(f"错误: {msg}")
            return False
        
        # 重置密码
        hashed_password = auth_service.hash_password(new_password)
        cursor = db.conn.cursor()
        cursor.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user["id"])
        )
        db.conn.commit()
        
        print(f"✓ 成功重置用户 '{username}' 的密码")
        print(f"  用户ID: {user['id']}")
        print(f"  角色: {user.get('role', 'user')}")
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_admin_user(username: str, password: str):
    """创建管理员用户"""
    try:
        from core.database import get_database
        from services.auth_service import get_auth_service
        
        db = get_database()
        auth_service = get_auth_service()
        
        # 检查用户是否已存在
        existing_user = db.get_user_by_username(username)
        if existing_user:
            print(f"用户 '{username}' 已存在，将重置密码")
            return reset_password(username, password)
        
        # 验证密码强度
        valid, msg = auth_service.validate_password_strength(password)
        if not valid:
            print(f"错误: {msg}")
            return False
        
        # 创建用户
        hashed_password = auth_service.hash_password(password)
        user_id = auth_service.create_user(username, password, role="admin", email="")
        
        print(f"✓ 成功创建管理员用户 '{username}'")
        print(f"  用户ID: {user_id}")
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def list_users():
    """列出所有用户"""
    try:
        from core.database import get_database
        
        db = get_database()
        users = db.get_all_users()
        
        if not users:
            print("数据库中没有用户")
            return
        
        print("用户列表:")
        print("-" * 60)
        print(f"{'ID':<5} {'用户名':<20} {'角色':<10} {'状态':<10}")
        print("-" * 60)
        for user in users:
            print(f"{user['id']:<5} {user['username']:<20} {user.get('role', 'user'):<10} {user.get('status', 'active'):<10}")
        print("-" * 60)
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  重置密码: python scripts/reset-admin-password.py <username> <new_password>")
        print("  创建用户: python scripts/reset-admin-password.py --create <username> <password>")
        print("  列出用户: python scripts/reset-admin-password.py --list")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        list_users()
    elif sys.argv[1] == "--create":
        if len(sys.argv) < 4:
            print("错误: 需要提供用户名和密码")
            sys.exit(1)
        username = sys.argv[2]
        password = sys.argv[3]
        create_admin_user(username, password)
    else:
        if len(sys.argv) < 3:
            print("错误: 需要提供用户名和新密码")
            sys.exit(1)
        username = sys.argv[1]
        password = sys.argv[2]
        reset_password(username, password)


