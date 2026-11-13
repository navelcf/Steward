# 只做业务判断

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

# `IntegrityError` 是 SQLAlchemy 的一个异常类，含义是「数据库的完整性约束被违反了」。
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.auth.models import User
from steward.modules.auth.repository import UserRepository  # 看邮箱是否注册
from steward.modules.auth.schemas import RegisterIn  # 注册接口契约
from steward.modules.auth.security import create_access_token, hash_password, verify_password  # 密码，签发token


# 业务异常；router 捕获后转成 HTTP 状态码，service 自己不碰 HTTPException。
class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = UserRepository(session)  # UserRepository对象
        self.session = session

    # 注册：查重 -> 哈希 -> 落库 -> 提交。
    async def register(self, body: RegisterIn) -> User:
        if await self.repo.get_by_email(str(body.email)) is not None:
            raise AuthError("邮箱已注册")

        user = await self.repo.create(
            email=str(body.email),
            password_hash=hash_password(body.password),
            display_name=body.display_name,
        )

        # 先查再插之间有竞态：两个请求同时通过查重时，唯一约束会在这里抛 IntegrityError。
        # 必须捕获并 rollback，否则 Session 停在失败状态，后续请求全挂。
        try:
            await self.session.commit()  # 正式入数据库
        except IntegrityError as exc:
            # 唯一约束被违反（`unique=True` 的列插了重复值）→这里就是这种
            await self.session.rollback()
            raise AuthError("邮箱已注册") from exc
        return user

    # 登录：失败信息统一，不区分「用户不存在」和「密码错误」，避免枚举账号。
    # 这考虑地也太细致了！！但是枚举出注册邮箱貌似也没什么用吧
    async def login(self, email: str, password: str) -> str:
        user = await self.repo.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("邮箱或密码错误")
        if not user.is_active:
            raise AuthError("用户已禁用")
        return create_access_token(user.id)
