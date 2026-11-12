# 放所有表模型共用的地基：一个 Base 基类，两个时间戳 Mixin。
# Day 3 的 User、Day 4 的 ChatThread 都会写成 class User(Base, CreatedAtMixin, UpdatedAtMixin)。


from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
# **`DeclarativeBase` 是什么：** SQLAlchemy 提供的一个基类，继承它就获得「我能被映射成表」的能力。


# ORM = 把「数据库表」映射成「Python 类」。
# 所有 ORM 表模型的基类。Day 3 的 User、Day 4 的 ChatThread 都继承它。
# 类体不能只有注释（Python 会把空类体当语法错误），所以这里写 pass。
# ORM 写法：
# user = await session.get(User, 1)
# email = user.email      # ← 直接点属性


class Base(DeclarativeBase):
    pass


# 只想要创建时间的表继承这个；mapped_column 在 Mixin 里会被 SQLAlchemy 复制到子类。
class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())  # datatime列


# 需要「最后修改时间」的表再继承这个；onupdate 让 UPDATE 时自动刷新。
class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        # `onupdate` 干的事：每次 UPDATE 这一行时，自动把这一列刷成当前时间。
    )
