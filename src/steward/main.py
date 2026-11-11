from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from steward.core.config import settings
from steward.core.logging import configure_logging, get_logger

# 初始化日志系统
configure_logging(settings.logging.level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 应用生命周期：外部资源只在这里创建和释放。

    # 方案 12.2 第 3 条：禁止模块级创建连接/客户端。
    # Day 2 会在这里加 check_database() / close_database()。

    logger.info("应用启动", app=settings.app.name, port=settings.app.port)
    yield
    logger.info("应用关闭", app=settings.app.name)


# 初始化fastapi
app = FastAPI(
    title=settings.app.name,
    version="0.1.0",
    debug=settings.app.debug,
    lifespan=lifespan,
)


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
