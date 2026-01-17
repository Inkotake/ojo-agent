# -*- coding: utf-8 -*-
"""
项目信息 API 路由 v9.0

提供更新日志和用户反馈功能:
- 更新日志: 版本更新记录, 支持小红点未读提醒
- 用户反馈: 功能建议/Bug报告/问题咨询
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, List
from loguru import logger

from core.database import get_database
from api.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/project", tags=["project"])


# ==================== 数据模型 ====================

class ChangelogCreate(BaseModel):
    """创建更新日志请求"""
    version: str
    title: str
    content: str
    type: str = "feature"  # feature/bugfix/improvement/breaking
    is_published: bool = False


class ChangelogUpdate(BaseModel):
    """更新更新日志请求"""
    version: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    type: Optional[str] = None
    is_published: Optional[bool] = None


class MarkReadRequest(BaseModel):
    """标记已读请求"""
    changelog_id: int


class FeedbackCreate(BaseModel):
    """创建反馈请求"""
    type: str  # feature/bug/question/other
    title: str
    content: str


class FeedbackReply(BaseModel):
    """管理员回复反馈请求"""
    status: Optional[str] = None  # pending/reviewing/planned/completed/rejected
    priority: Optional[int] = None
    admin_reply: Optional[str] = None


# ==================== 更新日志 API ====================

@router.get("/changelogs")
async def get_changelogs(
    limit: int = 20,
    include_drafts: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    获取更新日志列表
    
    - 普通用户: 只能看到已发布的更新日志
    - 管理员: 可通过 include_drafts=true 查看草稿
    """
    db = get_database()
    is_admin = current_user.get("role") == "admin"
    
    # 非管理员强制不显示草稿
    show_drafts = include_drafts and is_admin
    
    changelogs = db.get_changelogs(include_drafts=show_drafts, limit=limit)
    latest_id = db.get_latest_published_changelog_id()
    
    return {
        "changelogs": changelogs,
        "latest_id": latest_id,
        "total": len(changelogs)
    }


@router.get("/changelogs/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """
    获取未读更新日志数量
    
    用于前端小红点显示:
    - unread_count > 0: 显示小红点
    - latest_id: 最新已发布的更新日志ID
    """
    db = get_database()
    user_id = current_user["user_id"]
    
    unread_count = db.get_unread_changelog_count(user_id)
    latest_id = db.get_latest_published_changelog_id()
    
    return {
        "unread_count": unread_count,
        "latest_id": latest_id
    }


@router.post("/changelogs/mark-read")
async def mark_changelog_read(
    request: MarkReadRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    标记更新日志为已读
    
    用户查看更新日志页面后调用，清除小红点
    """
    db = get_database()
    user_id = current_user["user_id"]
    
    db.mark_changelog_read(user_id, request.changelog_id)
    
    logger.debug(f"用户 {user_id} 标记更新日志 {request.changelog_id} 为已读")
    
    return {"success": True}


@router.get("/changelogs/{changelog_id}")
async def get_changelog_detail(
    changelog_id: int,
    current_user: dict = Depends(get_current_user)
):
    """获取单个更新日志详情"""
    db = get_database()
    changelog = db.get_changelog_by_id(changelog_id)
    
    if not changelog:
        raise HTTPException(status_code=404, detail="更新日志不存在")
    
    # 非管理员不能查看未发布的
    is_admin = current_user.get("role") == "admin"
    if not changelog.get("is_published") and not is_admin:
        raise HTTPException(status_code=404, detail="更新日志不存在")
    
    return changelog


@router.post("/changelogs")
async def create_changelog(
    request: ChangelogCreate,
    current_user: dict = Depends(require_admin)
):
    """
    创建更新日志（管理员）
    
    - is_published=false: 保存为草稿
    - is_published=true: 直接发布
    """
    db = get_database()
    user_id = current_user["user_id"]
    
    changelog_id = db.create_changelog(
        version=request.version,
        title=request.title,
        content=request.content,
        type=request.type,
        created_by=user_id,
        is_published=request.is_published
    )
    
    # 如果直接发布，更新发布时间
    if request.is_published:
        db.update_changelog(changelog_id, is_published=True)
    
    logger.info(f"管理员 {user_id} 创建更新日志 {changelog_id}: {request.title}")
    
    db.log_activity(user_id, "create_changelog", f"changelog:{changelog_id}", {
        "version": request.version,
        "title": request.title,
        "is_published": request.is_published
    })
    
    return {
        "success": True,
        "changelog_id": changelog_id,
        "message": "更新日志已发布" if request.is_published else "草稿已保存"
    }


@router.put("/changelogs/{changelog_id}")
async def update_changelog(
    changelog_id: int,
    request: ChangelogUpdate,
    current_user: dict = Depends(require_admin)
):
    """更新更新日志（管理员）"""
    db = get_database()
    user_id = current_user["user_id"]
    
    # 检查是否存在
    changelog = db.get_changelog_by_id(changelog_id)
    if not changelog:
        raise HTTPException(status_code=404, detail="更新日志不存在")
    
    success = db.update_changelog(
        changelog_id,
        version=request.version,
        title=request.title,
        content=request.content,
        type=request.type,
        is_published=request.is_published
    )
    
    if success:
        logger.info(f"管理员 {user_id} 更新了更新日志 {changelog_id}")
        db.log_activity(user_id, "update_changelog", f"changelog:{changelog_id}", {
            "changes": request.model_dump(exclude_none=True)
        })
    
    return {"success": success}


@router.post("/changelogs/{changelog_id}/publish")
async def publish_changelog(
    changelog_id: int,
    current_user: dict = Depends(require_admin)
):
    """
    发布更新日志（管理员）
    
    将草稿状态的更新日志设为已发布，触发所有用户的小红点
    """
    db = get_database()
    user_id = current_user["user_id"]
    
    changelog = db.get_changelog_by_id(changelog_id)
    if not changelog:
        raise HTTPException(status_code=404, detail="更新日志不存在")
    
    if changelog.get("is_published"):
        return {"success": True, "message": "已经是发布状态"}
    
    success = db.update_changelog(changelog_id, is_published=True)
    
    if success:
        logger.info(f"管理员 {user_id} 发布了更新日志 {changelog_id}")
        db.log_activity(user_id, "publish_changelog", f"changelog:{changelog_id}")
    
    return {"success": success, "message": "更新日志已发布"}


@router.delete("/changelogs/{changelog_id}")
async def delete_changelog(
    changelog_id: int,
    current_user: dict = Depends(require_admin)
):
    """删除更新日志（管理员）"""
    db = get_database()
    user_id = current_user["user_id"]
    
    changelog = db.get_changelog_by_id(changelog_id)
    if not changelog:
        raise HTTPException(status_code=404, detail="更新日志不存在")
    
    success = db.delete_changelog(changelog_id)
    
    if success:
        logger.info(f"管理员 {user_id} 删除了更新日志 {changelog_id}")
        db.log_activity(user_id, "delete_changelog", f"changelog:{changelog_id}")
    
    return {"success": success}


# ==================== 用户反馈 API ====================

@router.get("/feedbacks")
async def get_feedbacks(
    status: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    获取反馈列表
    
    - 普通用户: 只能看到自己提交的反馈
    - 管理员: 可以看到所有反馈
    """
    db = get_database()
    user_id = current_user["user_id"]
    is_admin = current_user.get("role") == "admin"
    
    # 非管理员只能看自己的反馈
    query_user_id = None if is_admin else user_id
    
    feedbacks = db.get_feedbacks(
        user_id=query_user_id,
        status=status,
        type=type,
        limit=limit
    )
    
    return {
        "feedbacks": feedbacks,
        "total": len(feedbacks)
    }


@router.post("/feedbacks")
async def create_feedback(
    request: FeedbackCreate,
    current_user: dict = Depends(get_current_user)
):
    """提交反馈"""
    db = get_database()
    user_id = current_user["user_id"]
    
    # 验证类型
    valid_types = ["feature", "bug", "question", "other"]
    if request.type not in valid_types:
        raise HTTPException(
            status_code=400, 
            detail=f"无效的反馈类型，允许: {', '.join(valid_types)}"
        )
    
    feedback_id = db.create_feedback(
        user_id=user_id,
        type=request.type,
        title=request.title,
        content=request.content
    )
    
    logger.info(f"用户 {user_id} 提交反馈 {feedback_id}: [{request.type}] {request.title}")
    
    db.log_activity(user_id, "create_feedback", f"feedback:{feedback_id}", {
        "type": request.type,
        "title": request.title
    })
    
    return {
        "success": True,
        "feedback_id": feedback_id,
        "message": "反馈已提交，感谢您的反馈！"
    }


@router.get("/feedbacks/{feedback_id}")
async def get_feedback_detail(
    feedback_id: int,
    current_user: dict = Depends(get_current_user)
):
    """获取单个反馈详情"""
    db = get_database()
    user_id = current_user["user_id"]
    is_admin = current_user.get("role") == "admin"
    
    feedback = db.get_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    
    # 非管理员只能查看自己的反馈
    if not is_admin and feedback.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权查看此反馈")
    
    return feedback


@router.put("/feedbacks/{feedback_id}/reply")
async def reply_feedback(
    feedback_id: int,
    request: FeedbackReply,
    current_user: dict = Depends(require_admin)
):
    """
    管理员回复反馈
    
    可更新: status, priority, admin_reply
    """
    db = get_database()
    admin_id = current_user["user_id"]
    
    feedback = db.get_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    
    # 验证状态
    if request.status:
        valid_statuses = ["pending", "reviewing", "planned", "completed", "rejected"]
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"无效的状态，允许: {', '.join(valid_statuses)}"
            )
    
    success = db.update_feedback(
        feedback_id,
        status=request.status,
        priority=request.priority,
        admin_reply=request.admin_reply,
        admin_id=admin_id
    )
    
    if success:
        logger.info(f"管理员 {admin_id} 回复了反馈 {feedback_id}")
        db.log_activity(admin_id, "reply_feedback", f"feedback:{feedback_id}", {
            "status": request.status,
            "has_reply": bool(request.admin_reply)
        })
    
    return {"success": success}


@router.delete("/feedbacks/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    删除反馈
    
    - 普通用户: 只能删除自己的反馈
    - 管理员: 可以删除任何反馈
    """
    db = get_database()
    user_id = current_user["user_id"]
    is_admin = current_user.get("role") == "admin"
    
    feedback = db.get_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    
    # 非管理员只能删除自己的反馈
    if not is_admin and feedback.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权删除此反馈")
    
    success = db.delete_feedback(feedback_id)
    
    if success:
        logger.info(f"用户 {user_id} 删除了反馈 {feedback_id}")
        db.log_activity(user_id, "delete_feedback", f"feedback:{feedback_id}")
    
    return {"success": success}

