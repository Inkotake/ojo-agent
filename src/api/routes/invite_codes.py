# -*- coding: utf-8 -*-
"""
邀请码管理 API 路由

管理员可以生成、查看、删除邀请码
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import secrets
from loguru import logger

from core.database import get_database
from api.dependencies import get_current_user, require_admin


router = APIRouter()


# ==================== 数据模型 ====================

class CreateInviteCodeRequest(BaseModel):
    note: Optional[str] = None
    expires_days: Optional[int] = 30  # 默认30天过期


class InviteCodeResponse(BaseModel):
    id: int
    code: str
    created_by: int
    creator_name: Optional[str]
    used_by: Optional[int]
    used_by_name: Optional[str]
    note: Optional[str]
    created_at: str
    used_at: Optional[str]
    expires_at: Optional[str]
    status: str  # 'available', 'used', 'expired'


# ==================== 路由 ====================

@router.get("", response_model=List[InviteCodeResponse])
async def get_invite_codes(current_user: dict = Depends(require_admin)):
    """获取所有邀请码（管理员）"""
    db = get_database()
    codes = db.get_all_invite_codes()
    
    result = []
    now = datetime.now()
    
    for code in codes:
        # 计算状态
        if code.get('used_by'):
            code_status = 'used'
        elif code.get('expires_at'):
            expires = datetime.fromisoformat(code['expires_at']) if isinstance(code['expires_at'], str) else code['expires_at']
            code_status = 'expired' if expires < now else 'available'
        else:
            code_status = 'available'
        
        result.append({
            **code,
            'status': code_status,
            'created_at': str(code.get('created_at', '')),
            'used_at': str(code.get('used_at', '')) if code.get('used_at') else None,
            'expires_at': str(code.get('expires_at', '')) if code.get('expires_at') else None,
        })
    
    return result


@router.post("", response_model=InviteCodeResponse)
async def create_invite_code(
    request: CreateInviteCodeRequest,
    current_user: dict = Depends(require_admin)
):
    """生成新邀请码（管理员）"""
    db = get_database()
    
    # 生成随机码 (8位字母数字)
    code = secrets.token_urlsafe(6)[:8].upper()
    
    # 计算过期时间
    expires_at = None
    if request.expires_days and request.expires_days > 0:
        expires_at = (datetime.now() + timedelta(days=request.expires_days)).isoformat()
    
    # 创建邀请码
    code_id = db.create_invite_code(
        code=code,
        created_by=current_user['user_id'],
        note=request.note,
        expires_at=expires_at
    )
    
    logger.info(f"管理员 {current_user['username']} 创建邀请码: {code}")
    db.log_activity(current_user['user_id'], 'create_invite_code', target=code)
    
    return {
        'id': code_id,
        'code': code,
        'created_by': current_user['user_id'],
        'creator_name': current_user['username'],
        'used_by': None,
        'used_by_name': None,
        'note': request.note,
        'created_at': datetime.now().isoformat(),
        'used_at': None,
        'expires_at': expires_at,
        'status': 'available'
    }


@router.delete("/{code_id}")
async def delete_invite_code(
    code_id: int,
    current_user: dict = Depends(require_admin)
):
    """删除邀请码（管理员）"""
    db = get_database()
    
    success = db.delete_invite_code(code_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="邀请码不存在"
        )
    
    logger.info(f"管理员 {current_user['username']} 删除邀请码 ID: {code_id}")
    db.log_activity(current_user['user_id'], 'delete_invite_code', target=str(code_id))
    
    return {"message": "邀请码已删除"}


@router.get("/stats")
async def get_invite_stats(current_user: dict = Depends(require_admin)):
    """获取邀请码统计（管理员）"""
    db = get_database()
    codes = db.get_all_invite_codes()
    
    now = datetime.now()
    total = len(codes)
    used = sum(1 for c in codes if c.get('used_by'))
    expired = sum(1 for c in codes if not c.get('used_by') and c.get('expires_at') and 
                  datetime.fromisoformat(c['expires_at']) < now)
    available = total - used - expired
    
    return {
        'total': total,
        'available': available,
        'used': used,
        'expired': expired
    }
