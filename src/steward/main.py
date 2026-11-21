from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from steward.core.config import settings
from steward.core.logging import configure_logging, get_logger

from steward.infra.database import close_database, init_database  # 将数据库连接系统接入了

from steward.common.models import Base
from steward.modules.auth.models import User
from steward.modules.auth.router import router as auth_router

from steward.modules.thread.models import ChatThread
from steward.modules.thread.router import router as thread_router

from steward.modules.file.router import router as file_router

from steward.infra.llm import init_llm
from steward.modules.chat.router import router as chat_router

from steward.modules.chat.history_router import router as history_router
from steward.modules.chat.models import Message

from steward.infra.checkpointer import close_checkpointer, init_checkpointer
from steward.modules.tool.models import ToolRegistry
from steward.modules.tool.router import router as tool_router
from steward.modules.tool.service import ensure_registered

from steward.modules.approval.models import Approval
from steward.modules.approval.router import router as approval_router

from steward.modules.trace.models import RunTrace
from steward.modules.trace.router import router as trace_router


from steward.infra.milvus import close_milvus, init_milvus

from steward.modules.knowledge.models import Document, ParentChunk
from steward.modules.knowledge.router import router as knowledge_router

from steward.modules.memory.models import Memory
from steward.modules.memory.router import router as memory_router

from steward.modules.eval.models import EvalCaseResult, EvalRun

from fastapi.middleware.cors import CORSMiddleware

# 初始化日志系统
configure_logging(settings.logging.level)
logger = get_logger(__name__)


# 初始化生命周期钩子
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # 异步生成器对象，none为「吐出来的东西的类型」
    # 应用生命周期：外部资源只在这里创建和释放。

    # 方案 12.2 第 3 条：禁止模块级创建连接/客户端。
    # Day 2 会在这里加 check_database() / close_database()。

    logger.info("应用启动", app=settings.app.name, port=settings.app.port)
    await init_database(app)
    # 读一下 User.__tablename__：既确认模型已被 import 注册到 Base.metadata，也留一条可查的日志。
    # 少了这一步，create_all 可能安静地建成 0 张表（静默错误）。
    # 读一次两个模型的 __tablename__：确保都已注册进 Base.metadata，并留可查的哨兵日志。
    logger.info(
        "待建表",
        tables=[
            User.__tablename__,
            ChatThread.__tablename__,
            Message.__tablename__,
            ToolRegistry.__tablename__,
            Approval.__tablename__,
            RunTrace.__tablename__,
            Document.__tablename__,
            ParentChunk.__tablename__,
            Memory.__tablename__,
            EvalCaseResult.__tablename__,
            EvalRun.__tablename__,
        ],
    )
    async with app.state.db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # `Base.metadata` 是一份记录所有表定义的登记表。它是一个 `MetaData` 对象。
        # `create_all` 是同步方法，它要的是一条同步的 `Connection`
        # `conn.run_sync`：在线程中运行同步代码。也就是说，这里会等它
    logger.info("数据表已就绪", tables=sorted(Base.metadata.tables))

    await init_checkpointer(app)  # 创建 Checkpointer连接
    await ensure_registered(app.state.db_session_factory)
    # 就是这里，必须先自己开一个session
    # `Depends` 是 FastAPI 替你开；`async with factory()` 是你自己开
    # 这里必须自己借用工厂开一条，没有http请求

    init_llm(app)

    init_milvus(app)
    # 同步，会卡哦，但是没关系，一次性的
    # `MilvusClient` 没有；异步要用 `pymilvus.AsyncMilvusClient` 这个另一套类

    try:
        yield
    finally:
        close_milvus(app)
        await close_checkpointer(app)  # 先关 Checkpointer 的 psycopg 池，再关 SQLAlchemy 的 asyncpg 池
        await close_database(app)
        logger.info("应用关闭", app=settings.app.name)


# 初始化fastapi
app = FastAPI(
    title=settings.app.name,
    version="0.1.0",
    debug=settings.app.debug,
    lifespan=lifespan,
    docs_url="/docs-Navelcf25",
    redoc_url=None,
    openapi_url="/openapi-Navelcf25.json"
)

# 前端 localhost:3000 要跨域调 8001；Bearer token 走 header，不用 cookie，所以不开 credentials。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # SSE 不需要额外暴露 header，但加上无害，方便以后读 X-Request-Id。
    expose_headers=["*"],
)

# router 自带 prefix，这里不要再传 prefix
app.include_router(auth_router)
# 挂上身份认证路由

app.include_router(thread_router)
# 挂上会话管理路由

app.include_router(file_router)
# 挂上文件管理路由

app.include_router(chat_router)
# 挂上聊天路由

app.include_router(history_router)
# 挂上历史路由

app.include_router(tool_router)
# 挂上工具路由

app.include_router(approval_router)
# 挂上审批卡片路由

app.include_router(trace_router)
# 挂上跟踪路由

app.include_router(knowledge_router)
# 挂上RAG路由

app.include_router(memory_router)
# 挂上长期记忆路由


# 测试接口
@app.get("/health", summary="健康检查", tags=["ops"])
async def health() -> dict[str, str]:
    # 给探活和 Day 2 的健康检查用；今天只返回静态 ok。
    logger.info("健康检测接口正常调用")
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "steward.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=True,
        reload_dirs=["src"],  # 只盯 src，不盯 .venv
    )
