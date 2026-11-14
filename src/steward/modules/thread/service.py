# 业务判断

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.thread.models import ChatThread
from steward.modules.thread.repository import ThreadRepository
from steward.modules.thread.schemas import ThreadCreateIn


# 业务异常；「不存在」和「不是你的」合并成同一个，router 统一转 404。
class ThreadNotFoundError(Exception):
    pass


# 只做业务判断，不碰 Request、不写 SQL、不认识 HTTP 状态码。
class ThreadService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ThreadRepository(session)
        self.session = session

    async def list_threads(self, user_id: int, limit: int, offset: int) -> Sequence[ChatThread]:
        return await self.repo.list_by_user(user_id, limit, offset)
        # 问题在这里，后端列出来所有的thread_id，后端不负责记，前端记住就行了。

    async def create_thread(self, user_id: int, body: ThreadCreateIn) -> ChatThread:
        # uuid4() 返回 UUID 对象，必须转 str 才能塞进 String(36)。
        thread = await self.repo.create(
            thread_id=str(uuid4()),
            # 纯随机，理论上应该重复概率很低
            user_id=user_id,
            title=body.title or "新会话",
        )
        await self.session.commit()
        return thread

    async def rename_thread(self, thread_id: str, user_id: int, title: str) -> ChatThread:
        thread = await self.repo.get_owned(thread_id, user_id)
        if thread is None:
            raise ThreadNotFoundError()
        await self.repo.rename(thread, title)
        await self.session.commit()
        return thread

    async def delete_thread(self, thread_id: str, user_id: int) -> None:
        thread = await self.repo.get_owned(thread_id, user_id)
        if thread is None:
            raise ThreadNotFoundError()
        await self.repo.remove(thread)
        await self.session.commit()
