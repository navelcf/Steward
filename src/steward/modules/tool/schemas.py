from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# 策略三档（方案 9.2 L1053–1057）；Literal 让非法值在入参层就 422。
ToolPolicy = Literal["auto", "ask", "deny"]
# Literal 约束字段值为指定的常量


# 注册表出参；不暴露 server_cfg（可能含连接配置），也不暴露内部 id。
class ToolOut(BaseModel):
    name: str
    display_name: str | None
    source: str
    description: str
    policy: ToolPolicy
    risk_note: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# 改策略的入参；只接受这一个字段，多传的键被忽略。
class PolicyUpdateIn(BaseModel):
    policy: ToolPolicy = Field(description="auto 直接执行 / ask 暂停等人确认 / deny 直接拒绝")
