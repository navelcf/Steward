# `dependencies` 的缩写。在 FastAPI 里，它指的是“请求进来时、路由函数执行之前，先自动跑一遍的东西”
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.auth.models import User
from steward.modules.chat.schemas import ChatIn
from steward.modules.thread.models import ChatThread
from steward.modules.thread.repository import ThreadRepository


# 普通 async def 依赖：函数体在 SSE 响应头发出之前就执行完，404 才回得来。
# body 与路径函数共享同一个 ChatIn 实例，FastAPI 不会解析两次（本机实测）。
# get_current_user 内部也 Depends(get_session)，FastAPI 的依赖缓存会让两处拿到同一个 session，不会开两条连接。
async def get_owned_thread(
    body: ChatIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatThread:
    thread = await ThreadRepository(session).get_owned(body.thread_id, current_user.id)
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return thread
