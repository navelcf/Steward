# 一摸一样的结构，这个专门操作数据库用，存放东西
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.chat.models import Message


# 只做 messages 表的数据访问；每个查询都把 user_id 下推到 WHERE（方案 4.6）。
class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 历史按 id 升序（自增 id 天然保序），带分页；查不到别人的会话就是空列表。
    async def list_by_thread(self, thread_id: str, user_id: int, limit: int, offset: int) -> Sequence[Message]:
        stmt = (
            select(Message)
            .where(Message.thread_id == thread_id, Message.user_id == user_id)
            .order_by(Message.id.asc())  # 升序
            .limit(limit)  # 一页最多多少
            .offset(offset)
        )
        return (await self.session.scalars(stmt)).all()
        # 现在看到已经很熟悉了

    # 总数给分页用；同样带 user_id，别裸 count 全表。
    async def count_by_thread(self, thread_id: str, user_id: int) -> int:
        stmt = (
            select(func.count()).select_from(Message).where(Message.thread_id == thread_id, Message.user_id == user_id)
        )
        # SELECT count(*) FROM messages WHERE messages.thread_id = ? AND messages.user_id = ?
        return await self.session.scalar(stmt) or 0


    # 这个会话里某个角色有几条；用来判断「是不是新会话首轮」。
    async def count_by_role(self, thread_id: str, user_id: int, role: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Message)
            .where(
                Message.thread_id == thread_id,
                Message.user_id == user_id,
                Message.role == role,
            )
        )
        return await self.session.scalar(stmt) or 0

    # 只 flush 不 commit：由 service 决定事务边界。
    async def add(self, message: Message) -> None:
        self.session.add(message)
        await self.session.flush()

    # 清空按 user_id + thread_id 一起删；返回实际删除行数，方便日志与排查。
    async def delete_by_thread(self, thread_id: str, user_id: int) -> int:
        stmt = delete(Message).where(Message.thread_id == thread_id, Message.user_id == user_id)
        # 这是删除语句，并非一个实际的删除动作
        result = await self.session.execute(stmt)
        return result.rowcount or 0
        # `await session.execute(stmt)` 的返回值里有个 `.rowcount`，意思是 “这次实际删了几行”。
