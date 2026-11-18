from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from steward.core.logging import get_logger
from steward.modules.tool.builtin import BUILTIN_META, SaveNoteArgs, build_save_note, get_current_time
from steward.modules.tool.models import ToolRegistry
from steward.modules.tool.repository import ToolRepository

from langchain.agents.middleware import InterruptOnConfig

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
        existing = {row.name for row in await repo.list_all()}  # 表里的所有名字
        added: list[str] = []
        for name, meta in BUILTIN_META.items():  # 键和值成对，我怎么连这个也忘记掉了
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


# 一次查出本轮的工具集与中断配置，避免同一张表查两遍。
# 返回：(可给模型的工具, 需要中断确认的配置)。
async def load_toolset(
    session: AsyncSession,
    user_id: int,
    note_id: str | None = None,
) -> tuple[list[BaseTool], dict[str, bool | InterruptOnConfig]]:
    rows: Sequence[ToolRegistry] = await ToolRepository(session).list_all()
    tools: list[BaseTool] = []
    interrupt_on: dict[str, bool | InterruptOnConfig] = {}
    # bool的话，LangChain 允许简写配置：（这里用不到，但要写）
    # interrupt_on = {
    #     "save_note":   True,      # True = 用默认配置（approve/edit/reject 都给）
    #     "get_time":    False,     # False = 不拦
    #     "delete_file": {"allowed_decisions": ["approve", "reject"]},   # 精细配置
    # }

    for row in rows:
        if not row.is_enabled or row.policy == "deny":
            continue
        if row.name == "get_current_time":
            tools.append(get_current_time)
        elif row.name == "save_note":
            tools.append(build_save_note(user_id, note_id))  # 这个和上面那个不一样，这个出来的就是一个basetool类
        else:
            logger.warning("注册表里有未知工具，跳过", tool=row.name)
            continue

        if row.policy == "ask":
            # 只给 approve / reject；edit 留 Day 4。
            interrupt_on[row.name] = {
                "allowed_decisions": ["approve", "reject"],
                "description": row.risk_note or f"工具 {row.name} 需要确认",
            }
            # 如果哪天觉得太烦（记个普通笔记也要确认一遍），可以配：
            # interrupt_on["save_note"] = {
            #     "allowed_decisions": ["approve", "reject"],
            #     "when": lambda req: "删除" in req.tool_call["args"].get("content", ""),
            # }
            # 只拦「内容里带删除」的调用，其他自动放行

    return tools, interrupt_on
