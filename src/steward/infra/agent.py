from __future__ import annotations

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph

from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig

# 系统提示词；今天只有一句，Day 3 之后按工作流分档再扩。
SYSTEM_PROMPT = "你是 Steward，一个严谨的中文助手。需要事实性信息时调用可用工具，不要编造；不确定就明说。"


# 纯内存编译，无 I/O；每次请求构造一次，让 policy 改动立刻生效。
def build_agent(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    checkpointer: AsyncPostgresSaver,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
) -> CompiledStateGraph:
    middleware: list[HumanInTheLoopMiddleware] = []
    if interrupt_on:
        # per_call：一个工具调用一张卡，payload 是单数（见 0.5 第 1 条）。
        middleware.append(
            HumanInTheLoopMiddleware(interrupt_on=interrupt_on, interrupt_mode="per_call")
            # Command(resume={"decisions": [{"type": "reject", "message": "语气太书面了"}]})
            # 上面是我老代码的写法，一次解决所有，per_call，每个工具调用单独一次中断
        )

    return create_agent(
        model=model,
        tools=list(tools),  # 我犯蠢了，（）是变成列表，[]是嵌套一层列表
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        middleware=middleware,
    )
