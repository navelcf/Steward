from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.approval.models import Approval


# 只做 approvals 表的数据访问；归属过滤一律下推 WHERE（方案 4.6）。
class ApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_owned(self, approval_id: str, user_id: int) -> Approval | None:
        return await self.session.scalar(
            select(Approval).where(
                Approval.id == approval_id,
                Approval.user_id == user_id,
            )
        )

    # 幂等
    async def get_by_key(self, idempotency_key: str) -> Approval | None:
        return await self.session.scalar(select(Approval).where(Approval.idempotency_key == idempotency_key))

    # 列表：user_id 下推 + 状态可选 + 按创建时间倒序，命中 idx_approvals_user_status。
    async def list_by_user(
        self,
        user_id: int,
        status: str | None,
        limit: int,
        offset: int,
    ) -> Sequence[Approval]:
        stmt = select(Approval).where(Approval.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Approval.status == status)
        stmt = stmt.order_by(Approval.created_at.desc()).limit(limit).offset(offset)
        return (await self.session.scalars(stmt)).all()

    async def add(self, row: Approval) -> None:
        self.session.add(row)
        await self.session.flush()

    # CAS：只有 pending 才能迁走；返回到影响行数，0 表示已被别人决策。
    # CAS = Compare And Swap，比较并交换。
    # 不能「先查状态再 update」—— 并发下两个请求都会通过（手册第五节红线）。
    # CAS 把「比较」和「修改」压进一条 SQL，PG 保证这条 SQL 是原子的。不然先查后改可能会有时间差
    async def decide_cas(
        self,
        approval_id: str,
        user_id: int,
        new_status: str,
        note: str | None,
    ) -> int:
        stmt = (
            update(Approval)
            .where(
                Approval.id == approval_id,
                Approval.user_id == user_id,  # 顺便再次校验归属
                Approval.status == "pending",
            )
            .values(  # 更新值
                status=new_status,
                decided_at=datetime.now(UTC),  # datetime.now(timezone.utc)这种写法一样的
                decision_note=note,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0
        #  同一时刻，只有一个请求能拿到 1。数据库的行锁排队。
