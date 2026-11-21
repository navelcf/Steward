from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from steward.common.models import Base, CreatedAtMixin


# 长期记忆：跨会话可复用的一句话结论，独立于 chat_threads（方案 8.4）。
class Memory(Base, CreatedAtMixin):
    __tablename__ = "memories"

    # 和项目其它表一致：uuid4 字符串，不依赖 PG 扩展。
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # task_result / decision / preference / fact（方案 8.2）
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # 去掉就认不出来的短标题；也是去重键的一部分。
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # 一句话结论，不存原文。
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 哪次运行产生的；点开能回溯到原始对话（方案 L151 验收项）。
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_doc_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 1~5；低于 3 不入库（方案 8.2）。
    importance: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    # 方案 8.2 说「同键已存在时 version+1」，但 4.3 的 DDL 没这一列，这里补上。
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 过期时间；今天不设，留位给「这条记忆只对某个季度有效」的场景。
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # 去重键：同一个用户的同类同标题只留一行，冲突时更新而不是插入。
        UniqueConstraint("user_id", "kind", "title", name="uq_memories_user_kind_title"),
        # 召回查询的形状：我的 → 按 kind / 时间（方案 4.3 的索引）。
        Index("idx_memories_user_kind", "user_id", "kind", "created_at"),
        CheckConstraint(
            "kind IN ('task_result', 'decision', 'preference', 'fact')",
            name="ck_memories_kind",
        ),
        CheckConstraint("importance BETWEEN 1 AND 5", name="ck_memories_importance"),
    )
