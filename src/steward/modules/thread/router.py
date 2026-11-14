from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status

# FastAPI 收到 `Query` 标签卡后，在请求进来时执行校验
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.auth.models import User
from steward.modules.thread.models import ChatThread
from steward.modules.thread.schemas import ThreadCreateIn, ThreadOut, ThreadUpdateIn
from steward.modules.thread.service import ThreadNotFoundError, ThreadService

# 和 auth 一样，prefix 写全；main.py 里 include_router 不要再叠 prefix。
router = APIRouter(prefix="/api/v1/threads", tags=["thread"])


# 列自己的会话；limit/offset 由 Query 卡范围，避免负数或一次捞全表。
@router.get("", response_model=list[ThreadOut])
async def list_threads(
    limit: int = Query(default=20, ge=1, le=100),  # >=1,<=100
    offset: int = Query(default=0, ge=0),  # >=0
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Sequence[ChatThread]:  # 对这个列表里面的每个元素，都应用 ThreadOut 模型，出来又是一个新列表！
    return await ThreadService(session).list_threads(current_user.id, limit, offset)


# 新建；user_id 只从登录态取，请求体里没有也不接受 user_id。
@router.post("", response_model=ThreadOut, status_code=201)
async def create_thread(
    body: ThreadCreateIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatThread:
    return await ThreadService(session).create_thread(current_user.id, body)


# 改名；查不到（不存在或不是自己的）一律 404，不返回 403。
@router.patch("/{thread_id}", response_model=ThreadOut)  # 前端把这个thread_id带过来
async def rename_thread(
    thread_id: str,
    body: ThreadUpdateIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatThread:
    try:
        return await ThreadService(session).rename_thread(thread_id, current_user.id, body.title)
    except ThreadNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在") from exc
        # 404 这个路径根本没有
        # 405 这个路径有，但你用的方法不对，这个还是别用


# 删除成功返回 204，不能有响应体。
@router.delete("/{thread_id}", status_code=204)  # 204 “成功，但没有内容”
async def delete_thread(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await ThreadService(session).delete_thread(thread_id, current_user.id)
    except ThreadNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在") from exc
