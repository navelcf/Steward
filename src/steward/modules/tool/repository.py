from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.tool.models import ToolRegistry


# 只做 tool_registry 的数据访问；不做业务判断，不决定默认值。
class ToolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 按 name 稳定排序，方便 curl 对照。
    async def list_all(self) -> Sequence[ToolRegistry]:
        stmt = select(ToolRegistry).order_by(ToolRegistry.name.asc())  # asc() 升序
        return (await self.session.scalars(stmt)).all()

    async def get_by_name(self, name: str) -> ToolRegistry | None:
        return await self.session.scalar(select(ToolRegistry).where(ToolRegistry.name == name))

    # 只 flush 不 commit：事务边界由 service 决定。
    async def add(self, row: ToolRegistry) -> None:
        self.session.add(row)
        await self.session.flush()

    # 直接改 ORM 对象的字段，靠 UpdatedAtMixin 的 onupdate 自动刷新时间戳。
    async def set_policy(self, row: ToolRegistry, policy: str) -> ToolRegistry:
        row.policy = policy
        await self.session.flush()
        await self.session.refresh(row)
        return row
