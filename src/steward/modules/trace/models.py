from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from steward.common.models import Base, CreatedAtMixin


# 一次运行的步骤流水；step 在同一 run_id 内从 1 递增，回放按它排序。
class RunTrace(Base, CreatedAtMixin):
    __tablename__ = "run_traces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 业务 run_id：首轮生成，恢复轮次复用（靠 messages.run_id 传递）。
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)  # 任务，或者说轮次id，一次完整
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
    step: Mapped[int] = mapped_column(Integer, nullable=False)  # 同一个 run_id 内从 1 递增
    # model / tool / approval / error 四类（方案 4.3 L455）。
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )  # 具体叫什么：模型名、工具名、卡片 id、错误类型
    # 方案 DDL 就叫 input / output；存截断后的摘要，绝不存全文（见坑表 6）。
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 这步的输入（JSONB）。模型步放本轮消息摘要，工具步放参数 `{"content": "..."}`
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 这步的输出（JSONB）。模型步放回复摘要，工具步放返回值 `"4/xxx.md"`
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 这步花了几毫秒
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 输入 token 数（只有模型步有，工具步是 NULL）
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 输出 token 数（同上）

    __table_args__ = (
        CheckConstraint(
            "kind IN ('model', 'tool', 'approval', 'error')",
            name="ck_run_traces_kind",
        ),
        Index("idx_run_traces_run_step", "run_id", "step"),
        Index("idx_run_traces_user_created", "user_id", "created_at"),
    )
