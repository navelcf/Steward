from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.auth.models import User
from steward.modules.chat.schemas import MessageListOut
from steward.modules.chat.service import HistoryService, ThreadNotFoundError

# 路径对齐方案 5.3 的 /threads/{id}/messages；单独一个 router 是因为 prefix 不同。
router = APIRouter(prefix="/api/v1/threads", tags=["chat"])


# 历史消息；带分页，按时间升序。会话不是自己的一律 404。
@router.get("/{thread_id}/messages", response_model=MessageListOut)
async def list_messages(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageListOut:
    try:
        return await HistoryService(session).list_messages(thread_id, current_user.id, limit, offset)
    except ThreadNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在") from exc


# 清空该会话的消息；204 无响应体。
@router.delete("/{thread_id}/messages", status_code=204)
async def clear_messages(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await HistoryService(session).clear_messages(thread_id, current_user.id)
    except ThreadNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在") from exc
