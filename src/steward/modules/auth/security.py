# 密码哈希和 JWT 签发/校验。

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# datetime,类，某个时刻
# timedelta,类，一段时间
# timezone,类，时区，`timezone.utc` = UTC 时区
import jwt
from pwdlib import PasswordHash

# PasswordHash是一个类
from steward.core.config import settings

password_hash = PasswordHash.recommended()
# pwdlib 的 PasswordHash.recommended() 默认挑 argon2id
# password_hash是PasswordHash类的实例
ALGORITHM = "HS256"
# HS256：HMAC + SHA256，对称签名算法。签名和验签用同一把密钥（就是settings.auth.secret）


# 把 JWT 相关异常收敛成自己的异常类型，上层只认 TokenError。
class TokenError(Exception):
    pass


# 注册时调用：输入明文，输出 argon2 哈希串，只存这一串到 users.password_hash。
def hash_password(raw: str) -> str:
    return password_hash.hash(raw)


# 登录时调用：拿用户输入的明文和库里的哈希比对，永不还原原文。
def verify_password(raw: str, hashed: str) -> bool:
    return password_hash.verify(raw, hashed)


# 登录成功后签发；sub 按 JWT 规范存字符串，exp 用带时区的 UTC 时间。
def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        # subject，这里存 user_id（转成字符串，JWT 规范要求是字符串，某些库解码后不做转换会踩坑）
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.auth.expire_minutes),
        # 过期时间，用 datetime.now(timezone.utc) + timedelta(...)，必须带时区
        # UTC 是全世界的基准时间
    }
    return jwt.encode(payload, settings.auth.secret, algorithm=ALGORITHM)


# 验签并取出 user_id；失败抛 TokenError，由 deps.py 转成 401。
def decode_token(token: str) -> int:  # `decode` 内部有一行 `if exp <= now`对比过期
    try:
        payload = jwt.decode(token, settings.auth.secret, algorithms=[ALGORITHM])
        # `decode` 内部有一行 `if exp <= now`对比过期
        # 内部直接比较过第三段的数据
    except jwt.PyJWTError as exc:  # 捕获 decode 内部所有报错
        raise TokenError("登录已失效") from exc

    subject = payload.get("sub")
    # payload["sub"] → 键不存在时抛KeyError
    # payload.get("sub") → 键不存在时返回None
    # 用.get意味着：不管 token 里有没有sub，你都能拿到一个值（可能是 `None`），然后自己判断。
    if subject is None:
        raise TokenError("登录已失效")
    return int(subject)  # 判断还没有结束，还要去数据库查这个用户的真实情况
