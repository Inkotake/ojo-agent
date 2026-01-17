# -*- coding: utf-8 -*-
"""
SHSOJ文本清洗API
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from loguru import logger

router = APIRouter()


class WashPreviewRequest(BaseModel):
    """清洗预览请求"""
    problem_ids: List[str]
    fields: List[str] = ["description", "input", "output", "hint"]
    sensitive_words: Optional[List[str]] = None


class WashExecuteRequest(BaseModel):
    """清洗执行请求"""
    problem_ids: List[str]
    fields: List[str] = ["description", "input", "output", "hint"]
    sensitive_words: Optional[List[str]] = None
    dry_run: bool = False


class WashResult(BaseModel):
    """清洗结果"""
    problem_id: str
    field: str
    original: str
    cleaned: str
    changes: int


class WashResponse(BaseModel):
    """清洗响应"""
    success: bool
    message: str
    results: List[WashResult] = []
    total_changes: int = 0


# 默认敏感词列表
DEFAULT_SENSITIVE_WORDS = [
    "上海市", "上海", "Shanghai", "shanghai",
    "学校", "中学", "小学", "高中", "初中",
    "班级", "年级", "学号", "姓名",
    "电话", "手机", "地址", "邮箱",
    "真实", "实际", "考试", "测试",
]


def clean_text(text: str, sensitive_words: List[str]) -> tuple[str, int]:
    """
    清洗文本，移除敏感词
    
    Returns:
        (cleaned_text, change_count)
    """
    if not text:
        return text, 0
    
    cleaned = text
    changes = 0
    
    for word in sensitive_words:
        if word in cleaned:
            count = cleaned.count(word)
            cleaned = cleaned.replace(word, "***")
            changes += count
    
    return cleaned, changes


@router.post("/preview", response_model=WashResponse)
async def preview_wash(request: WashPreviewRequest):
    """
    预览清洗结果
    
    Args:
        request: 清洗预览请求
    
    Returns:
        预览结果
    """
    try:
        from services.oj.registry import get_global_registry
        
        sensitive_words = request.sensitive_words or DEFAULT_SENSITIVE_WORDS
        results = []
        total_changes = 0
        
        # 获取适配器
        registry = get_global_registry()
        adapter = registry.get_adapter("shsoj")
        
        if not adapter:
            raise HTTPException(status_code=400, detail="SHSOJ适配器未配置")
        
        auth = adapter.login()
        if not auth:
            raise HTTPException(status_code=401, detail="登录失败")
        
        # 获取题目数据并预览清洗
        for pid in request.problem_ids[:50]:  # 限制最多50个
            try:
                # 获取题目详情
                fetcher = adapter.get_problem_fetcher()
                problem = fetcher.fetch_problem(pid) if fetcher else None
                
                if not problem:
                    continue
                
                for field in request.fields:
                    original = problem.get(field, "")
                    if not original:
                        continue
                    
                    cleaned, changes = clean_text(original, sensitive_words)
                    
                    if changes > 0:
                        results.append(WashResult(
                            problem_id=str(pid),
                            field=field,
                            original=original[:200] + "..." if len(original) > 200 else original,
                            cleaned=cleaned[:200] + "..." if len(cleaned) > 200 else cleaned,
                            changes=changes
                        ))
                        total_changes += changes
                        
            except Exception as e:
                logger.warning(f"预览题目 {pid} 失败: {e}")
                continue
        
        return WashResponse(
            success=True,
            message=f"预览完成，共发现 {total_changes} 处需要清洗",
            results=results,
            total_changes=total_changes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清洗预览失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=WashResponse)
async def execute_wash(request: WashExecuteRequest, background_tasks: BackgroundTasks):
    """
    执行清洗
    
    Args:
        request: 清洗执行请求
        background_tasks: 后台任务
    
    Returns:
        执行结果
    """
    if request.dry_run:
        # Dry run模式，只返回预览
        preview_req = WashPreviewRequest(
            problem_ids=request.problem_ids,
            fields=request.fields,
            sensitive_words=request.sensitive_words
        )
        return await preview_wash(preview_req)
    
    try:
        from services.oj.registry import get_global_registry
        
        sensitive_words = request.sensitive_words or DEFAULT_SENSITIVE_WORDS
        
        # 获取适配器
        registry = get_global_registry()
        adapter = registry.get_adapter("shsoj")
        
        if not adapter:
            raise HTTPException(status_code=400, detail="SHSOJ适配器未配置")
        
        auth = adapter.login()
        if not auth:
            raise HTTPException(status_code=401, detail="登录失败")
        
        # 后台执行清洗
        background_tasks.add_task(
            _execute_wash_batch,
            adapter,
            auth,
            request.problem_ids,
            request.fields,
            sensitive_words
        )
        
        return WashResponse(
            success=True,
            message=f"清洗任务已开始，将处理 {len(request.problem_ids)} 个题目",
            results=[],
            total_changes=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行清洗失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _execute_wash_batch(
    adapter: Any,
    auth: Any,
    problem_ids: List[str],
    fields: List[str],
    sensitive_words: List[str]
):
    """后台执行批量清洗"""
    try:
        import time
        
        fetcher = adapter.get_problem_fetcher()
        uploader = adapter.get_data_uploader()
        
        for pid in problem_ids:
            try:
                # 获取题目
                problem = fetcher.fetch_problem(pid) if fetcher else None
                if not problem:
                    continue
                
                # 清洗各字段
                updated = False
                for field in fields:
                    original = problem.get(field, "")
                    if not original:
                        continue
                    
                    cleaned, changes = clean_text(original, sensitive_words)
                    if changes > 0:
                        problem[field] = cleaned
                        updated = True
                
                # 更新题目
                if updated and uploader and hasattr(uploader, 'update_problem'):
                    uploader.update_problem(auth, pid, problem)
                    logger.info(f"清洗题目 {pid} 完成")
                
                # 限速
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"清洗题目 {pid} 失败: {e}")
                continue
                
        logger.info(f"批量清洗完成，共处理 {len(problem_ids)} 个题目")
        
    except Exception as e:
        logger.error(f"批量清洗失败: {e}", exc_info=True)


@router.get("/sensitive-words")
async def get_sensitive_words():
    """获取默认敏感词列表"""
    return {
        "words": DEFAULT_SENSITIVE_WORDS,
        "count": len(DEFAULT_SENSITIVE_WORDS)
    }
