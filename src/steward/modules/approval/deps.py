# 把 404/409 挪到响应头之前
# HTTPException 写在函数体里，响应头 200 已经出去了，404/409 根本回不来。
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.approval.models import Approval
from steward.modules.approval.repository import ApprovalRepository
from steward.modules.auth.models import User


# 第一层：存在 + 归属。查不到一律 404，不区分「不存在」和「不是你的」。
async def get_owned_approval(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Approval:
    row = await ApprovalRepository(session).get_owned(approval_id, current_user.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "审批不存在")
    return row


# 第二层：状态 + 有效期。依赖链会在响应头之前跑完，409 回得去。
async def get_pending_approval(
    approval: Approval = Depends(get_owned_approval),
) -> Approval:
    if approval.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "审批已处理")
    if approval.expires_at is not None and datetime.now(UTC) > approval.expires_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "审批已过期")
    return approval
