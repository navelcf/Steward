# 配置大模型的连接信息
from __future__ import annotations

from fastapi import FastAPI
from langchain.chat_models import init_chat_model

from steward.core.config import settings
from steward.core.logging import get_logger

logger = get_logger(__name__)


# 在 lifespan 里调用；模块级不建客户端（方案 12.2 第 3 条）。
def init_llm(app: FastAPI) -> None:
    # 用 OpenAI 兼容格式直连 DeepSeek，不用厂商专用类；换模型只改 .env 的 CHAT_MODEL。
    app.state.chat_model = init_chat_model(
        model=settings.llm.chat_model,
        model_provider="openai",
        api_key=settings.llm.api_key,
        base_url=settings.llm.base_url,
        # 991808 约等于 1M 减预留：不显式告诉 LangChain，它会按 8192 估算，文档一长就在客户端侧误判超限。
        profile={"max_input_tokens": 991808},
        # 官方思考模式默认开启；这里显式关掉，温度参数才会生效（见教程 3.6.3）。
        extra_body={"thinking": {"type": settings.llm.thinking}},
        # temperature 在思考模式不生效；默认已关闭思考，这个值才真正起作用。
        temperature=settings.llm.temperature,
        stream_usage=settings.llm.stream_usage,      # ← 加这一行，才有token
    )
    logger.info(
        "模型客户端就绪",
        model=settings.llm.chat_model,
        base_url=settings.llm.base_url,
        thinking=settings.llm.thinking,
        max_input_tokens=991808,
    )
