from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from steward.common.models import Base, CreatedAtMixin


# 审批卡；一次中断一张，pending 时等人决策，决策后不再变。
# 字段照方案 4.3 L430-446；外键按方案 4.4 L531 统一 CASCADE。
class Approval(Base, CreatedAtMixin):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid生成
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    # P1 没有 task 概念，先留 NULL；P3 做长任务时再接 tasks 表。
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    args_json: Mapped[dict] = mapped_column(JSONB, nullable=False)  # 模型填的参数
    # 用户改过的参数；今天是 NULL，Day 4 的 edit 分支才会写。
    edited_args: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # 幂等键：sha256(thread_id + interrupt_id + tool_name)，唯一约束兜底。
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    # LangGraph 的中断 id；Day 4 多卡 resume 时必须用它指定「解哪一张」。
    # 今天一定要建这一列：create_all 不会给已存在的表加列，Day 4 再补就得手写 ALTER。
    interrupt_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 用户决策时的备注
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 手册 Day 4 要验「过期后不可执行」；今天建字段，默认 24 小时。
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="ck_approvals_status",
        ),
        # 列表查询必然是「我的 + 某个状态 + 按时间倒序」，三列一起建。
        Index("idx_approvals_user_status", "user_id", "status", "created_at"),
    )
