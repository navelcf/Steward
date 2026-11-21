from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.memory.models import Memory


# 只做 memories 表的数据访问；每个查询都把 user_id 下推到 WHERE。
class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 召回：重要度优先、同重要度按时间倒序。条数少时这比向量召回更可控。
    async def list_for_recall(
        self,
        user_id: int,
        limit: int,
        min_importance: int,
    ) -> Sequence[Memory]:
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id, Memory.importance >= min_importance)
            .order_by(Memory.importance.desc(), Memory.created_at.desc())
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all()

    # 去重键查找：同一用户同类同标题只该有一行。
    async def get_by_key(self, user_id: int, kind: str, title: str) -> Memory | None:
        return await self.session.scalar(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.kind == kind,
                Memory.title == title,
            )
        )

    async def add(self, row: Memory) -> None:
        self.session.add(row)
        await self.session.flush()

    # 列出来给 GET /memories 和调试用；时间倒序。
    async def list_all(self, user_id: int, limit: int) -> Sequence[Memory]:
        stmt = select(Memory).where(Memory.user_id == user_id).order_by(Memory.created_at.desc()).limit(limit)
        return (await self.session.scalars(stmt)).all()
