# 只做数据访问
# 也就是往user表里搬运东西，只做处理，理论上处理应该在service层通过校验之类的
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.auth.models import User


# 只负责把 User 表的数据搬进搬出，不做任何业务判断（不判断「是否已注册」、不校验密码）。
class UserRepository:
    def __init__(self, session: AsyncSession) -> None:  # 一条Session连接
        self.session = session

    # 按邮箱查；where 由 SQLAlchemy 参数化绑定，杜绝 SQL 注入。
    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))
        # `scalar` 是「执行 + 只取第一个结果」的合体
        # 写的时候不是SQL，是一个 Python 对象（`Select`）。
        # 只有在执行的那一刻（`scalar`/`execute`），SQLAlchemy 才把它编译成真正的SQL字符串发出去。
        # 能这么写最根本还是因为User(Base, CreatedAtMixin, UpdatedAtMixin)继承了Base，获得了orm能力

    # 只 flush 拿回自增 id，不 commit —— 事务边界交给 service 统一控制。
    async def create(self, email: str, password_hash: str, display_name: str | None) -> User:
        user = User(email=email, password_hash=password_hash, display_name=display_name)
        self.session.add(user)  # 登记，不发 SQL
        # async_sessionmaker(bind=engine, autoflush=False, ...)显式关掉了 autoflush
        await self.session.flush()  # 发 INSERT，我要获得自增 id，才能签发token！
        await self.session.refresh(user)  # 没啥用，可以删掉
        return user
