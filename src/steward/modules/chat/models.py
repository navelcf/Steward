# 对话表
from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text

# Text:不设长度上的字符串
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from steward.common.models import Base, CreatedAtMixin


# 对话消息；一个会话有多条，按 user_id + thread_id 一起过滤（方案 4.6）。
# sources / run_id 是给 P2 引用溯源与 W2 Day 5 轨迹留的位，今天始终为 NULL。
class Message(Base, CreatedAtMixin):
    __tablename__ = "messages"

    # 自增 BIGINT：消息要严格保序，created_at 在同一事务里可能相同。
    # 因为created_at，一次请求里写了两条消息（你的问题 + 模型的回答），两条的 `created_at`完全相同
    # 因为你的 `CreatedAtMixin` 用的是 `server_default=func.now()`，
    # 而 PostgreSQL 的 `now()` 返回的是事务开始时间—— 同一条事务里，无论调多少次，都返回同一个值。
    # 因此需要自增id作为主键，来进行排序。
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        # ondelete="CASCADE"：父行被删掉时，子行跟着一起删
        nullable=False,
    )
    # 冗余存一列，是为了把 user_id 过滤下推到 SQL，不用先 join chat_threads。
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    # `JSONB`：PostgreSQL 专属的 JSON 类型（`B` = binary，存的是解析后的二进制结构）。
    # `sources` = “这条回答引用了哪些文档片段”
    # data: {"sources": [{"source_id": "ref-001", "doc_id": "...", "clause_name": "合同.pdf",
    # "section_path": "3.2", "content": "……"}]}

    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # `run_id` = “这一次运行的编号”
    # 这就是可回放的关键！

    __table_args__ = (
        # `__table_args__` 这个名字不能改。它是 SQLAlchemy 约定好的。
        Index("idx_messages_user_thread_id", "user_id", "thread_id", "id"),
        # 第一个元素是索引名，三个一起的索引名
        # 因为查询的时候必然是这种结构："我的（user_id）这个会话（thread_id）的消息，按 id 排"
        Index("idx_messages_run", "run_id"),
        CheckConstraint("role IN ('user', 'assistant', 'tool')", name="ck_messages_role"),
        # 检查约束：role 列的值只能是 'user'、'assistant' 或 'tool'，约束
    )
