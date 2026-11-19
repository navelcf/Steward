from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.trace.models import RunTrace


# 只做 run_traces 的数据访问；user_id 一律下推 WHERE（方案 4.6）。
class TraceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 回放用：按 step 升序，归属过滤在 SQL 里。
    async def list_by_run(self, run_id: str, user_id: int) -> Sequence[RunTrace]:
        stmt = (
            select(RunTrace)
            .where(RunTrace.run_id == run_id, RunTrace.user_id == user_id)
            .order_by(RunTrace.step.asc())# 升序
        )
        return (await self.session.scalars(stmt)).all()

    # 按会话列出全部步骤；前端自己按 run_id 分组。
    async def list_by_thread(
        self,
        thread_id: str,
        user_id: int,
        limit: int,
    ) -> Sequence[RunTrace]:
        stmt = (
            select(RunTrace)
            .where(RunTrace.thread_id == thread_id, RunTrace.user_id == user_id)
            .order_by(RunTrace.created_at.desc(), RunTrace.step.asc())
            .limit(limit)
            # 这个接口要的是「最近 N 条」，不是「第 3 页」。
            # 没人会翻到第 10 页去看三个月前的轨迹。用户想看的是「刚才这次运行怎么回事」，最多回溯最近几十次。
        )
        return (await self.session.scalars(stmt)).all()

    # 恢复轮次接着已有 step 往后排；没有记录就返回 0。
    # 这是resume干的事情，所以你要从同一个任务接上。
    async def max_step(self, run_id: str) -> int:
        stmt = select(func.max(RunTrace.step)).where(RunTrace.run_id == run_id)
        return await self.session.scalar(stmt) or 0

    # 批量落库；调用方负责 commit。
    async def add_all(self, rows: Sequence[RunTrace]) -> None:
        self.session.add_all(list(rows))
        await self.session.flush()