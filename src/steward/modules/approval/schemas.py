from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# 状态与决策都用 Literal：非法值在入参/出参层就 422，不进业务逻辑。
ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]
DecisionType = Literal["approve", "reject", "edit"]


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
    decision: DecisionType = Field(description="approve 批准 / reject 拒绝/ edit 改参数后执行")
    note: str | None = Field(default=None, max_length=500, description="可选备注，回给模型看")
    edited_args: dict | None = Field(default=None, description="edit 时替换工具参数的完整新参数")

    # `mode="after"`。
    # 含义：「等所有字段都校验通过、类型都转好了、模型对象已经组装成形，再跑这段代码。」
    @model_validator(mode="after")
    def check_edited_args(self) -> "DecisionIn":
        # edit 没参数 = 不知道该执行什么；其他决策带参数 = 前端传错了。
        if self.decision == "edit" and not self.edited_args:
            raise ValueError("edit 必须提供 edited_args")
        if self.decision != "edit" and self.edited_args is not None:
            raise ValueError("只有 edit 才能带 edited_args")
        return self
        # `mode="after"` 的返回值，会用来「替换」整个模型实例。必须return
