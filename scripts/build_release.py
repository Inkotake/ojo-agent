#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OJO v9.0 发布包构建脚本

生成可直接部署的 ZIP 压缩包，包含：
- src/ (源码)
- config/ (配置示例)
- scripts/ (部署脚本)
- docs/ (文档)
- requirements.txt (依赖)
- tests/ (测试用例)
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path
from datetime import datetime


def get_project_root():
    """获取项目根目录"""
    return Path(__file__).parent.parent


def clean_pycache(directory: Path):
    """清理 __pycache__ 目录"""
    for pycache in directory.rglob('__pycache__'):
        if pycache.is_dir():
            shutil.rmtree(pycache)
    for pyc in directory.rglob('*.pyc'):
        pyc.unlink()
    for pyo in directory.rglob('*.pyo'):
        pyo.unlink()


def build_release():
    """构建发布包"""
    project_root = get_project_root()
    
    # 版本号和时间戳
    version = "9.0.0"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    release_name = f"ojo_v{version}_{timestamp}"
    
    # 构建目录
    build_dir = project_root / "build" / release_name
    zip_path = project_root / "dist" / f"{release_name}.zip"
    
    print(f"=" * 60)
    print(f"  OJO v{version} 发布包构建")
    print(f"=" * 60)
    print(f"项目根目录: {project_root}")
    print(f"构建目录: {build_dir}")
    print(f"输出文件: {zip_path}")
    print()
    
    # 清理旧构建
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # 确保输出目录存在
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 要包含的目录和文件
    include_dirs = [
        ('src', 'src'),
        ('config', 'config'),
        ('scripts', 'scripts'),
        ('docs', 'docs'),
        ('tests', 'tests'),
    ]
    
    include_files = [
        'requirements.txt',
        'requirements_api.txt',
        '.env.example',
        'Dockerfile',
        'docker-compose.yml',
        '.gitignore',
        'README.md',
    ]
    
    # 排除的文件/目录模式
    exclude_patterns = [
        '__pycache__',
        '*.pyc',
        '*.pyo',
        '.git',
        '.idea',
        '.vscode',
        '.cursor',
        'venv',
        '.venv',
        '*.db',
        '*.db.backup',
        '*.log',
        'workspace',
        'logs',
        'temp',
        'node_modules',
        '.env',
        'config.json',
    ]
    
    def should_exclude(path: Path) -> bool:
        """检查是否应该排除"""
        name = path.name
        for pattern in exclude_patterns:
            if pattern.startswith('*'):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False
    
    def copy_directory(src: Path, dst: Path):
        """复制目录（排除指定模式）"""
        if not src.exists():
            print(f"  [跳过] 目录不存在: {src}")
            return
        
        dst.mkdir(parents=True, exist_ok=True)
        
        for item in src.iterdir():
            if should_exclude(item):
                continue
            
            target = dst / item.name
            if item.is_dir():
                copy_directory(item, target)
            else:
                shutil.copy2(item, target)
    
    # 复制目录
    print("[1/4] 复制源码和配置...")
    for src_name, dst_name in include_dirs:
        src_path = project_root / src_name
        dst_path = build_dir / dst_name
        print(f"  复制 {src_name}/ -> {dst_name}/")
        copy_directory(src_path, dst_path)
    
    # 复制文件
    print("[2/4] 复制根目录文件...")
    for filename in include_files:
        src_file = project_root / filename
        if src_file.exists():
            dst_file = build_dir / filename
            print(f"  复制 {filename}")
            shutil.copy2(src_file, dst_file)
        else:
            print(f"  [跳过] 文件不存在: {filename}")
    
    # 清理 __pycache__
    print("[3/4] 清理临时文件...")
    clean_pycache(build_dir)
    
    # 创建 ZIP
    print("[4/4] 创建 ZIP 压缩包...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in build_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(build_dir)
                zf.write(file_path, arcname)
    
    # 计算大小
    zip_size = zip_path.stat().st_size / (1024 * 1024)
    
    print()
    print(f"=" * 60)
    print(f"  构建完成!")
    print(f"=" * 60)
    print(f"输出文件: {zip_path}")
    print(f"文件大小: {zip_size:.2f} MB")
    print()
    print("部署说明:")
    print("  1. 解压 ZIP 到服务器")
    print("  2. 复制 .env.example 为 .env 并配置")
    print("  3. 运行 scripts/start.sh (Linux) 或 scripts/start.bat (Windows)")
    print("  4. 或使用 Docker: docker-compose up -d")
    
    return zip_path


if __name__ == "__main__":
    build_release()
