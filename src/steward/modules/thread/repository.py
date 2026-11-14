# 只做 chat_threads 表的数据访问。每一个查询都带 user_id，且下推到 SQL 的 WHERE

from __future__ import annotations

from collections.abc import Sequence  # 类型标注，一个有顺序的集合

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.thread.models import ChatThread


# 只搬数据，不做业务判断（不判断「该返回 404 还是 200」，不生成 uuid，不决定默认值）。
class ThreadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 列自己的会话；user_id 下推到 WHERE，按创建时间倒序，带分页。
    async def list_by_user(self, user_id: int, limit: int, offset: int) -> Sequence[ChatThread]:
        stmt = (
            select(ChatThread)
            .where(ChatThread.user_id == user_id)
            .order_by(ChatThread.created_at.desc())  # desc()降序
            .limit(limit)  # 最多几条
            .offset(offset)  # 跳过多少条
            # 每次递增，相当于翻页！
        )
        return (await self.session.scalars(stmt)).all()  # 可以.first取第一条
        # 这里是scalars，非 scalar，因为可能多条结果

    # 按 id + 归属一起查；查不到就是「不存在或不是你的」，上层统一转 404。
    async def get_owned(self, thread_id: str, user_id: int) -> ChatThread | None:
        return await self.session.scalar(
            select(ChatThread).where(
                ChatThread.id == thread_id,
                ChatThread.user_id == user_id,
            )
        )
        # 这里是 scalar，取第一条结果！

    # id 由 service 生成后传进来；flush 拿回数据库生成的时间戳，不 commit。
    async def create(self, thread_id: str, user_id: int, title: str) -> ChatThread:
        thread = ChatThread(id=thread_id, user_id=user_id, title=title)
        self.session.add(thread)
        await self.session.flush()
        await self.session.refresh(thread)  # 同样没啥用！
        return thread

    # 传入的 thread 已经由 get_owned 确认过归属，这里只改字段。
    async def rename(self, thread: ChatThread, title: str) -> ChatThread:
        thread.title = title
        await self.session.flush()
        await self.session.refresh(thread)
        return thread

    # AsyncSession.delete 是协程，别漏 await。
    async def remove(self, thread: ChatThread) -> None:
        await self.session.delete(thread)
        await self.session.flush()
