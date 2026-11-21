from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.eval.models import EvalCaseResult, EvalRun


class EvalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_run(self, row: EvalRun) -> None:
        self.session.add(row)
        await self.session.flush()

    async def add_results(self, rows: list[EvalCaseResult]) -> None:
        self.session.add_all(rows)
        await self.session.flush()

    # 按 label 取最近一次 run；对比时用。
    async def latest_by_label(self, label: str) -> EvalRun | None:
        return await self.session.scalar(
            select(EvalRun)
            .where(EvalRun.label == label)
            .order_by(EvalRun.created_at.desc())
            .limit(1)
        )

    async def list_runs(self, limit: int) -> list[EvalRun]:
        return list(
            (
                await self.session.scalars(
                    select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit)
                )
            ).all()
        )