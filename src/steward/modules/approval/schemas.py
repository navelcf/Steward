from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 状态与决策都用 Literal：非法值在入参/出参层就 422，不进业务逻辑。
ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]
DecisionType = Literal["approve", "reject"]


# 卡片出参；不暴露 idempotency_key / interrupt_id（内部用）和 user_id（最小暴露）。
# 前端只认 approval_id；Day 4 的 resume 由后端反查 interrupt_id，不把内部标识交给客户端。
class ApprovalOut(BaseModel):
    id: str
    thread_id: str
    tool_name: str
    args_json: dict
    edited_args: dict | None
    risk_note: str | None
    status: ApprovalStatus
    decided_at: datetime | None
    decision_note: str | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# 决策入参；今天只接受 approve / reject，edit 留 Day 4。
class DecisionIn(BaseModel):
    decision: DecisionType = Field(description="approve 批准 / reject 拒绝")
    note: str | None = Field(default=None, max_length=500, description="可选备注，回给模型看")
