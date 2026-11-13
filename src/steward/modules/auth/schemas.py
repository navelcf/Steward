# 定义 HTTP 层的出入参形状。
# FastAPI 拿它做校验和序列化：请求体不合法直接 422，响应自动按 response_model 过滤字段。
# 出入参定义 / 接口契约

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


# 注册入参；密码长度在入口就卡住，别等写到库里才发现问题。
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    display_name: str | None = None


# 登录入参；不限制长度上限之外的东西，避免泄露「什么样的密码算合法」。
class LoginIn(BaseModel):
    email: EmailStr
    password: str


# 登录出参；token_type 固定 bearer，前端拿去拼 Authorization 头。
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # 大小写不管。小写也能切


# 用户出参。故意不含 password_hash —— 响应模型就是最后一道防泄露闸门。
# from_attributes 让 Pydantic 能从 ORM 对象（User）直接读属性，不用手工转字典。
class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None

    model_config = {"from_attributes": True}
