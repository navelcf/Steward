# 定义 chat_threads 表：一个会话属于一个用户，记标题、当前工作流（P1 才用）、创建/更新时间。

from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column
# 依旧继承 Base

from steward.common.models import Base, CreatedAtMixin, UpdatedAtMixin


# 会话表；主键用 uuid4 字符串，避免自增 id 被枚举。
# user_id 建索引：本模块所有查询都带它，没索引会全表扫。
class ChatThread(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # 自己给，数据库不写
    # thread = ChatThread(id=str(uuid.uuid4()), user_id=..., title=...)
    # `uuid.uuid4()` 造出来的字符串是 36 个字符（带四个短横），刚好塞进 `String(36)`
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # 这里的 user_id 是外键，关联到 users 表的 id,但是属于逻辑外键，导入只会从user表里面存在的导入！
    # 一个用户必然有多个会话！所以不设unique！
    title: Mapped[str] = mapped_column(String(200), default="新会话", nullable=False)
    active_workflow: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # nullable完全是不必要写的！重复标注！
