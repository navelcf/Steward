# 放跨模块共用的 FastAPI 依赖。今天只有一个：get_current_user ——
# 从请求头取 Bearer token，解出 user_id，查库拿到 User。
# Day 4 之后的每个需要登录的接口都会 Depends(get_current_user)。

from __future__ import annotations

from fastapi import Depends, HTTPException, status

#
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# 凭证放在请求头里 —— 这是 HTTP 协议定的
# Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
# HTTPBearer：切出token的工具
# 切出来的两段装在这个盒子叫 `HTTPAuthorizationCredentials`
# `scheme`  认证方式
# `credentials`：token
from sqlalchemy.ext.asyncio import AsyncSession

from steward.infra.database import get_session
from steward.modules.auth.models import User
from steward.modules.auth.security import TokenError, decode_token

# auto_error=False：没带 token 时不让 FastAPI 直接抛 403，我们自己统一返回 401。
bearer = HTTPBearer(auto_error=False)
# 不是 403。403 会暗示「这个 id 存在但你没权限」，泄露信息；
# `HTTPBearer` 这个类里定义了 `__call__`。
# 一个类只要定义了 `__call__`，它的实例就能像函数一样被调用！和factor()一样
# 这句话只是造了一个 "切法"，还没用过。真正切的地方在 `__call__` 里面


# 取出当前登录用户；任何失败都是 401，且统一文案，不泄露账号是否存在。
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),  # 所以这里理论上是bearer(参数)
    session: AsyncSession = Depends(get_session),
) -> User:  # depends只管参数表，并非函数体
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")

    try:
        user_id = decode_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效") from exc

    user = await session.get(User, user_id)
    # `session.get(类, 主键值)` 是「按主键查一条」
    if user is None or not user.is_active:
        # 这里很重要，
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user
