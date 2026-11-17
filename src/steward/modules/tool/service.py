from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from steward.core.logging import get_logger
from steward.modules.tool.builtin import BUILTIN_META, SaveNoteArgs, build_save_note, get_current_time
from steward.modules.tool.models import ToolRegistry
from steward.modules.tool.repository import ToolRepository

logger = get_logger(__name__)


# 按 name 取工具的 JSON Schema；两个工具都实测能导出 properties / required。
def tool_param_schema(name: str) -> dict:
    if name == "save_note":
        return SaveNoteArgs.model_json_schema()
    if name == "get_current_time":
        return get_current_time.args_schema.model_json_schema()
    raise KeyError(f"未登记的内置工具: {name}")



# 启动时登记内置工具；只补缺失的行，绝不覆盖用户改过的 policy。
async def ensure_registered(factory: async_sessionmaker[AsyncSession]) -> None:
    # 它在 `lifespan` 里跑 —— 那时候还没有任何请求，自然也没有请求级的 session。
    # 所以它必须自己开一个
    async with factory() as session:
        repo = ToolRepository(session)
        existing = {row.name for row in await repo.list_all()}# 表里的所有名字
        added: list[str] = []
        for name, meta in BUILTIN_META.items():# 键和值成对，我怎么连这个也忘记掉了
            if name in existing:
                continue
            await repo.add(
                ToolRegistry(
                    name=name,
                    display_name=meta["display_name"],
                    source="builtin",
                    server_cfg=None,
                    param_schema=tool_param_schema(name),
                    description=meta["description"],
                    policy=meta["policy"],
                    risk_note=meta["risk_note"] or None,
                    is_enabled=True,
                    # `is_enabled=True` 是硬编码的，不是从 `BUILTIN_META` 读
                )
            )
            added.append(name)
        await session.commit()
    logger.info("工具注册表就绪", added=added, total=len(BUILTIN_META))


# 计算本次请求实际可用的工具集；deny 与 ask 今天都不给模型（见下方说明）。
async def available_tools(session: AsyncSession, user_id: int) -> list[BaseTool]:
    rows: Sequence[ToolRegistry] = await ToolRepository(session).list_all()
    tools: list[BaseTool] = []
    for row in rows:
        if not row.is_enabled or row.policy == "deny":
            continue
        if row.policy == "ask":
            # 过渡态：今天没有 HumanInTheLoopMiddleware，ask 工具若放进去会被直接执行。
            # Day 3 接上 interrupt_on 之后，这段改成「放进 tools，同时进 interrupt_on」。
            logger.info("ask 工具暂未接入中断", tool=row.name)
            continue
        if row.name == "get_current_time":
            tools.append(get_current_time)
        elif row.name == "save_note":
            tools.append(build_save_note(user_id))
    return tools