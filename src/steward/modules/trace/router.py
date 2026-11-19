from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.auth.models import User
from steward.modules.trace.repository import TraceRepository
from steward.modules.trace.schemas import TraceOut, TraceStepOut

router = APIRouter(prefix="/api/v1/traces", tags=["trace"])


# 按 run_id 回放；不是自己的 run 一律 404，不泄露「这个 run 存在」。
@router.get("/{run_id}", response_model=TraceOut)
async def get_trace(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TraceOut:
    rows = await TraceRepository(session).list_by_run(run_id, current_user.id)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "轨迹不存在")
    return TraceOut(
        run_id=run_id,
        thread_id=rows[0].thread_id,
        steps=[TraceStepOut.model_validate(row) for row in rows],
    )


# 按会话列出；前端按 run_id 自己分组。limit 是行数，不是 run 数。
@router.get("", response_model=list[TraceStepOut])
async def list_traces(
    thread_id: str = Query(min_length=36, max_length=36),
    limit: int = Query(default=200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TraceStepOut]:
    rows = await TraceRepository(session).list_by_thread(thread_id, current_user.id, limit)
    return [TraceStepOut.model_validate(row) for row in rows]
