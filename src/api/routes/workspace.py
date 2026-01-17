# -*- coding: utf-8 -*-
"""
工作区管理API路由
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pathlib import Path
import zipfile
import os
import tempfile
import json
from loguru import logger

from core.database import get_database
from .auth import get_current_user

router = APIRouter()


@router.get("/download/{task_id}")
async def download_workspace(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """下载任务工作区"""
    db = get_database()
    
    # 验证任务所有权（tasks 表的主键是 id，不是 task_id）
    try:
        task_id_int = int(task_id)
    except ValueError:
        logger.warning(f"无效的任务ID格式: task_id={task_id}")
        raise HTTPException(status_code=400, detail="无效的任务ID格式")
    
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, user_id, problem_id FROM tasks WHERE id = ?
    """, (task_id_int,))
    task_row = cursor.fetchone()
    
    if not task_row:
        logger.warning(f"任务不存在: task_id={task_id_int}, user_id={user.get('user_id')}")
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 将 Row 对象转换为字典
    task = dict(task_row)
    task_user_id = task["user_id"]
    user_id = user.get("user_id") or user.get("id")  # 兼容两种格式
    
    if task_user_id != user_id and user.get("role") != "admin":
        logger.warning(f"无权访问任务: task_id={task_id_int}, user_id={user_id}, task_user_id={task_user_id}")
        raise HTTPException(status_code=403, detail="无权访问此任务")
    
    # 查找工作区目录（使用 ProblemIdResolver 获取正确路径）
    from services.problem_id import get_problem_id_resolver
    problem_id = task["problem_id"]
    resolver = get_problem_id_resolver()
    workspace_path = resolver.get_workspace_dir(problem_id, task_user_id)
    
    logger.info(f"查找工作区: task_id={task_id_int}, problem_id={problem_id}, user_id={task_user_id}, path={workspace_path}")
    logger.info(f"工作区路径是否存在: {workspace_path.exists()}")
    
    # 检查父目录是否存在（可能工作区还没创建）
    if not workspace_path.exists():
        # 尝试列出可能的路径供调试
        parent_dir = workspace_path.parent
        logger.warning(f"工作区不存在: {workspace_path}")
        logger.info(f"父目录: {parent_dir}, 存在: {parent_dir.exists()}")
        if parent_dir.exists():
            try:
                existing_dirs = [d.name for d in parent_dir.iterdir() if d.is_dir()]
                logger.info(f"父目录下的现有目录: {existing_dirs[:10]}")  # 只显示前10个
            except Exception as e:
                logger.warning(f"无法列出父目录内容: {e}")
        raise HTTPException(status_code=404, detail=f"工作区不存在: {workspace_path}")
    
    # 创建ZIP文件（使用系统临时目录，兼容Docker环境）
    zip_filename = f"workspace_{task_id_int}.zip"
    temp_dir = Path(tempfile.gettempdir()) / "ojo_downloads"
    temp_dir.mkdir(exist_ok=True, mode=0o755)
    zip_path = temp_dir / zip_filename
    
    try:
        logger.info(f"打包工作区: {workspace_path} -> {zip_path}")
        logger.info(f"临时目录: {temp_dir}, 存在: {temp_dir.exists()}, 可写: {os.access(temp_dir, os.W_OK)}")
        
        file_count = 0
        
        # 从 problem_data.json 生成 problem_statement.md
        problem_data_path = workspace_path / "problem_data.json"
        problem_statement_md = None
        
        if problem_data_path.exists():
            try:
                with open(problem_data_path, 'r', encoding='utf-8') as f:
                    problem_data = json.load(f)
                
                # 生成 Markdown 格式的题目描述
                md_lines = []
                md_lines.append(f"# {problem_data.get('title', '题目')}\n")
                md_lines.append(f"**来源**: {problem_data.get('source', 'unknown')}  |  **题目ID**: {problem_data.get('id', 'N/A')}\n")
                
                if problem_data.get('description'):
                    md_lines.append(f"\n## 题目描述\n\n{problem_data['description']}\n")
                
                if problem_data.get('input_format'):
                    md_lines.append(f"\n## 输入格式\n\n{problem_data['input_format']}\n")
                
                if problem_data.get('output_format'):
                    md_lines.append(f"\n## 输出格式\n\n{problem_data['output_format']}\n")
                
                if problem_data.get('samples'):
                    md_lines.append(f"\n## 样例\n\n")
                    for i, sample in enumerate(problem_data['samples'], 1):
                        md_lines.append(f"### 样例 {i}\n\n")
                        md_lines.append(f"**输入**:\n```\n{sample.get('input', '')}\n```\n\n")
                        md_lines.append(f"**输出**:\n```\n{sample.get('output', '')}\n```\n\n")
                
                if problem_data.get('time_limit') or problem_data.get('memory_limit'):
                    md_lines.append(f"\n## 限制\n\n")
                    if problem_data.get('time_limit'):
                        md_lines.append(f"- **时间限制**: {problem_data['time_limit']} ms\n")
                    if problem_data.get('memory_limit'):
                        md_lines.append(f"- **内存限制**: {problem_data['memory_limit']} MB\n")
                
                if problem_data.get('hints'):
                    md_lines.append(f"\n## 提示\n\n{problem_data['hints']}\n")
                
                problem_statement_md = '\n'.join(md_lines)
                logger.debug(f"从 problem_data.json 生成了题目描述 Markdown")
            except Exception as e:
                logger.warning(f"读取 problem_data.json 失败: {e}")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. 添加 testcase 或 tests 文件夹
            testcase_dirs = ['testcase', 'tests']
            for testcase_dir in testcase_dirs:
                testcase_path = workspace_path / testcase_dir
                if testcase_path.exists() and testcase_path.is_dir():
                    logger.debug(f"添加测试数据文件夹: {testcase_dir}")
                    for root, dirs, files in os.walk(testcase_path):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(workspace_path)
                            zipf.write(file_path, arcname)
                            file_count += 1
                            if file_count <= 5:
                                logger.debug(f"添加文件到ZIP: {arcname}")
                    break  # 只添加第一个找到的测试数据文件夹
            
            # 2. 添加 solution.cpp 文件
            solution_cpp = workspace_path / "solution.cpp"
            if solution_cpp.exists():
                zipf.write(solution_cpp, "solution.cpp")
                file_count += 1
                logger.debug(f"添加文件到ZIP: solution.cpp")
            
            # 3. 添加生成的 problem_statement.md
            if problem_statement_md:
                zipf.writestr("problem_statement.md", problem_statement_md.encode('utf-8'))
                file_count += 1
                logger.debug(f"添加文件到ZIP: problem_statement.md (从 problem_data.json 生成)")
        
        if file_count == 0:
            logger.warning(f"工作区中没有可下载的文件: {workspace_path}")
            raise HTTPException(status_code=404, detail="工作区中没有可下载的文件（需要 testcase/tests 文件夹、solution.cpp 或 problem_data.json）")
        
        # 记录活动
        user_id = user.get("user_id") or user.get("id")  # 兼容两种格式
        db.log_activity(user_id, "download_workspace", target=str(task_id_int))
        
        zip_size = zip_path.stat().st_size
        logger.info(f"用户 {user.get('username', 'unknown')} 下载工作区: task_id={task_id_int}, {file_count} 个文件, ZIP大小: {zip_size} bytes")
        
        def cleanup_file():
            """清理临时文件（文件传输完成后由 FileResponse 触发）"""
            try:
                if zip_path.exists():
                    zip_path.unlink()
                    logger.debug(f"清理临时文件: {zip_path}")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")
        
        # 使用 FileResponse（FastAPI 内置的文件下载响应，更可靠）
        # FileResponse 会在文件发送完成后自动调用 background task
        return FileResponse(
            path=str(zip_path),
            filename=zip_filename,
            media_type="application/zip",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Accel-Buffering": "no"  # 禁用nginx缓冲（如果使用nginx）
            },
            background=BackgroundTask(cleanup_file)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"打包工作区失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"打包失败: {str(e)}")

