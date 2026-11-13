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
    logger.info("待建表", tables=[User.__tablename__])
    async with app.state.db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # `Base.metadata` 是一份记录所有表定义的登记表。它是一个 `MetaData` 对象。
        # `create_all` 是同步方法，它要的是一条同步的 `Connection`
        # `conn.run_sync`：在线程中运行同步代码。也就是说，这里会等它
    logger.info("数据表已就绪", tables=sorted(Base.metadata.tables))

    try:
        yield
    finally:
        await close_database(app)
    logger.info("应用关闭", app=settings.app.name)


# 初始化fastapi
app = FastAPI(
    title=settings.app.name,
    version="0.1.0",
    debug=settings.app.debug,
    lifespan=lifespan,
)

# router 自带 prefix，这里不要再传 prefix
app.include_router(auth_router)
# 挂上身份认证路由


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
