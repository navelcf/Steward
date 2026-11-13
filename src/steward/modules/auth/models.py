# 定义第一张业务表 users。继承 Day 2 的 Base 和两个时间戳 Mixin.
# 所以 created_at / updated_at 自动带上，不用重复写。

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
# 大整数类型，8字节，+-9.2e+18，Integer：4字节，SmallInteger：2字节
# `SMALLINT` 是给「明确知道范围」的列用的，比如「评分 1~5」。
# PG 的 `BOOLEAN` 还额外接受 `'t'` / `'f'` / `'1'` / `'0'` / `'yes'` / `'no'`
# 但存进去后统一显示为 `true` / `false`。

from sqlalchemy.orm import Mapped, mapped_column

from steward.common.models import Base, CreatedAtMixin, UpdatedAtMixin


# 用户表；继承 Base 获得映射能力，继承两个 Mixin 自动带 created_at / updated_at。
# 密码只存哈希，字段名写 password_hash，时刻提醒自己不要存明文。
class User(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # `autoincrement=True`
    # 这个参数是「让数据库自己往上涨」，不用你在 Python 里赋值。
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # `String(255)`：变长字符串，加一个长度上限
    # `unique=True` 这一列的值不能重复。
    # `index=True` 给这一列建一个索引。作用：查得快。
    password_hash: Mapped[str] = mapped_column(String(255))
    # argon2 的哈希串实测长度约 97 字符，`pbkdf2` 更长一些。255 给足余量。
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # `nullable=True` → 告诉数据库「这列可以为空」
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
