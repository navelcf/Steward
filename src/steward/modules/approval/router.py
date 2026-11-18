from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.approval.schemas import ApprovalOut, ApprovalStatus, DecisionIn
from steward.modules.approval.service import ApprovalConflictError, ApprovalService
from steward.modules.auth.models import User

router = APIRouter(prefix="/api/v1/approvals", tags=["approval"])


# 待确认卡片列表；status 不传就是全部。归属过滤在 repository 里下推。
@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalOut]:
    rows = await ApprovalService(session).list_approvals(current_user.id, status_filter, limit, offset)
    return [ApprovalOut.model_validate(row) for row in rows]


# 决策；不存在/不是你的 404，已处理 409。今天只落状态，不恢复 Agent（Day 4）。
@router.post("/{approval_id}/decide", response_model=ApprovalOut)
async def decide(
    approval_id: str,
    body: DecisionIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApprovalOut:
    try:
        row = await ApprovalService(session).decide(approval_id, current_user.id, body)
    except ApprovalConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "审批已处理") from exc
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "审批不存在")
    return ApprovalOut.model_validate(row)
