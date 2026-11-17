from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, CheckConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from steward.common.models import Base, CreatedAtMixin, UpdatedAtMixin


# 工具注册表；一行一个可调用工具，policy 决定模型能不能看见它、要不要停下来问。
class ToolRegistry(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "tool_registry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 自增主键
    # name 唯一：ensure_registered 靠它做幂等 upsert，也是 PUT /tools/{name}/policy 的键。
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="builtin")
    # MCP 保留位，今天不填；密钥绝不写进来。
    server_cfg: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # pydantic 导出的 JSON Schema（方案 9.1 L1036 / 9.3 L1063）。
    param_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # 给模型看的说明：必须写清「什么时候用、返回什么」。
    description: Mapped[str] = mapped_column(Text, nullable=False)
    policy: Mapped[str] = mapped_column(String(10), nullable=False, default="ask")
    risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 风险提示，给人看的
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 是否启用，这是总开关

    __table_args__ = (
        CheckConstraint(
            "policy IN ('auto', 'ask', 'deny')",
            name="ck_tool_registry_policy",
            # deny的话直接拒绝模型使用
        ),
        CheckConstraint(
            "source IN ('builtin', 'mcp')",
            name="ck_tool_registry_source",
        ),
    )
