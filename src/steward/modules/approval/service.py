from __future__ import annotations

import hashlib

# 算 sha256（幂等键）
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from langgraph.types import Interrupt
# value	停下来时「留在那张字条上的内容」
# {
#    "type": "tool_approval",
#     "tool_call_id": "call_1",
#     "name": "save_note",
#     "args": {"content": "Steward 接入 Agent 成功"},
#     "description": "工具 save_note 需要确认",
# }

# id	LangGraph 算出来的哈希，32 位十六进制
# response_schema	「你回信时请按这个格式写」

from sqlalchemy.ext.asyncio import AsyncSession

from steward.core.logging import get_logger
from steward.modules.approval.models import Approval
from steward.modules.approval.repository import ApprovalRepository
from steward.modules.approval.schemas import DecisionIn
from steward.modules.tool.repository import ToolRepository

logger = get_logger(__name__)

# 卡片有效期；Day 4 的 decide 会用它判过期。
CARD_TTL = timedelta(hours=24)  # 单纯表示一段时间
# datetime.now(UTC) + timedelta(hours=24)  # → 2026-11-19 18:00:12


# 审批单已处理过（并发或重复点击）；router 统一转 409。
class ApprovalConflictError(Exception):
    pass


# 卡片已过期；router 统一转 409（比 410 少一个状态码，前端好处理）。
class ApprovalExpiredError(Exception):
    pass


# 业务层：建卡、决策；不碰 Request、不返回 HTTP 状态码。
class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ApprovalRepository(session)

    # 用 interrupt 建一张卡；同一 interrupt 重试时复用已有单（幂等）。
    async def create_from_interrupt(
        self,
        thread_id: str,
        user_id: int,
        interrupt: Interrupt,
    ) -> Approval:
        payload = interrupt.value
        tool_name: str = payload["name"]
        args: dict = payload.get("args") or {}
        # `.get` 防 `KeyError`—— 万一某个工具 schema 里没有 args
        key = hashlib.sha256(f"{thread_id}:{interrupt.id}:{tool_name}".encode("utf-8")).hexdigest()

        existing = await self.repo.get_by_key(key)
        if existing is not None:
            return existing

        # risk_note 优先取注册表里人写的那句，比中间件的 description 更好读。
        tool_row = await ToolRepository(self.session).get_by_name(tool_name)
        risk_note = (tool_row.risk_note if tool_row else None) or payload.get("description")
        # 如果注册表里查到 save_note，且它有 risk_note → 用注册表那句（"将写入本地笔记文件"）
        # 否则 → 用中间件拼的那句（"工具 save_note 需要确认"）

        row = Approval(
            id=str(uuid4()),
            user_id=user_id,
            thread_id=thread_id,
            task_id=None,
            tool_name=tool_name,
            args_json=args,
            edited_args=None,
            risk_note=risk_note,
            status="pending",
            idempotency_key=key,
            interrupt_id=interrupt.id,
            expires_at=datetime.now(UTC) + CARD_TTL,  # 存入过期时间
        )
        await self.repo.add(row)
        await self.session.commit()
        logger.info("审批卡已创建", approval_id=row.id, tool=tool_name, thread_id=thread_id)
        return row

    async def list_approvals(
        self,
        user_id: int,
        status: str | None,
        limit: int,
        offset: int,
    ) -> Sequence[Approval]:
        return await self.repo.list_by_user(user_id, status, limit, offset)

    # 决策：过期校验 -> CAS 迁移 -> 返回最新快照；None 表示不存在或不是你的。
    async def decide(self, approval_id: str, user_id: int, body: DecisionIn) -> Approval | None:
        row = await self.repo.get_owned(approval_id, user_id)
        if row is None:
            return None

        # 过期先于 CAS：过期的卡不管并发与否都不该被执行。
        if row.expires_at is not None and datetime.now(UTC) > row.expires_at:
            await self.repo.decide_cas(approval_id, user_id, "expired", "卡片已过期")
            await self.session.commit()
            raise ApprovalExpiredError("审批已过期")

        new_status = "approved" if body.decision in ("approve", "edit") else "rejected"
        changed = await self.repo.decide_cas(
            approval_id,
            user_id,
            new_status,
            body.note,
            body.edited_args,
        )
        if changed == 0:
            await self.session.rollback()
            raise ApprovalConflictError("审批已处理")
        await self.session.commit()

        fresh = await self.repo.get_owned(approval_id, user_id)
        logger.info(
            "审批已决策",
            approval_id=approval_id,
            status=new_status,
            decision=body.decision,
            user_id=user_id,
        )
        return fresh
