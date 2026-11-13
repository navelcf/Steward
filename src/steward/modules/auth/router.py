# HTTP 层：收参数、调 AuthService、把 AuthError 翻成 HTTP 状态码。
# 不写 SQL、不碰 Request、不做业务判断
# `outer.py` 是唯一「知道 HTTP 存在」的那一层。
# 它不知道什么是事务、什么是哈希、什么是唯一约束。
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.auth.models import User
from steward.modules.auth.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from steward.modules.auth.service import AuthError, AuthService

# prefix 写全，main.py 里 include_router 时不要再叠 prefix，否则路径会变成 /api/v1/api/v1/auth/...
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])  # 造一个路由组
# 这个组里所有接口，路径前面自动加这一段。
# 写的是 `@router.post("/register")`，实际路径是 `/api/v1/auth/register`。
# `tags=["auth"]`：在 `/docs` 里归到「auth」这一组，页面上的折叠项。


# 注册成功返回 201，响应按 UserOut 过滤（不含 password_hash）。
@router.post("/register", response_model=UserOut, status_code=201)
# REST 规范用 201（Created），不是默认的 200。
async def register(body: RegisterIn, session: AsyncSession = Depends(get_session)) -> User:
    try:
        return await AuthService(session).register(body)
        # 这里返回的是 User对象，但是没关系，按 UserOut 过滤
        # UserOut 的配置: {'from_attributes': True}
        # `from_attributes=True` 的含义：允许 "从对象属性读"，而不是只能 "从字典读"。
    except AuthError as exc:
        raise HTTPException(400, str(exc)) from exc


# 登录返回 JWT；失败统一 401。
@router.post("/login", response_model=TokenOut)  # `没写 status_code`：默认 200。
async def login(body: LoginIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    try:
        token = await AuthService(session).login(str(body.email), body.password)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    return TokenOut(access_token=token)


# 需要登录才能访问；user 由依赖注入，函数体一行 SQL 都没有。
@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
