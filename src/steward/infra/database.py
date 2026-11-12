# 统一管理数据库这个外部资源：启动时建池并验证连通、给每个请求发一个独立 Session、
# 关闭时释放池。业务代码永远不自己 create_engine，也不自己拼连接串。

# 放在 infra/ 是因为方案 3.2 的分层：infra 管外部资源（换数据库实现只改这里），
# common 管共用基类，modules 管业务。

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,  # 类
    AsyncSession,  # 类
    async_sessionmaker,  # 类
    create_async_engine,  # 造连接池的函数
)

from steward.core.config import settings
from steward.core.logging import get_logger

# 不需要configure_logging(settings.logging.level)
logger = get_logger(__name__)


# 连接串由 config.py 统一提供，日志里只打 host/port/database，绝不打印 url（含密码）。
# 引擎和 session 工厂在 lifespan 里创建后挂到 app.state，模块级不建任何连接。
async def init_database(app: FastAPI) -> None:
    engine = create_async_engine(
        settings.db.url,  # 没有 `@property` 的情况，settings.db.url() 因为它是个方法
        echo=settings.db.echo,
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
        pool_recycle=settings.db.pool_recycle,
        pool_pre_ping=True,  # 每次从池里取连接前，先探一下「还活着吗」
    )

    # 立刻验证连通：连不上就在这里失败，别等到第一个请求才炸。
    # 失败时先把刚建好的池 dispose 掉，避免留下悬空资源。
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            # SQLAlchemy 2.0 不允许直接传字符串。
            # `text()` 是把字符串包装成「SQL 语句对象」，告诉 SQLAlchemy「这是真 SQL」。
    except Exception:
        await engine.dispose()
        raise

    app.state.db_engine = engine
    app.state.db_session_factory = async_sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )  # commit后保留orm对象的属性，这是一个异步session工厂
    logger.info(
        "数据库连接池初始化成功",
        host=settings.db.host,
        port=settings.db.port,
        database=settings.db.name,
        pool_size=settings.db.pool_size,
    )


# 关闭时调用；没初始化过就直接返回，保证重复调用也安全。
async def close_database(app: FastAPI) -> None:
    engine: AsyncEngine | None = getattr(app.state, "db_engine", None)
    if engine is None:
        logger.warning("数据库连接池未初始化，跳过关闭")
        return

    await engine.dispose()
    logger.info("数据库连接池已关闭")


# FastAPI 依赖注入用：每个请求借一条 Session，请求结束自动归还。
# Day 3 的 common/deps.py 会写 session: AsyncSession = Depends(get_session)


# 异步生成器对象AsyncGenerator
# 第一个 `AsyncSession`：每次 `yield session` 吐出去的是 Session，不接收东西
async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory
    # 它是泛型标注，读作 “async_sessionmaker 产出的东西是 AsyncSession”，和list[str]一样
    async with factory() as session:
        # with保证归还，`AsyncSession` 只定义了 `__aenter__` / `__aexit__`，没有 `__enter__` / `__exit__`。
        yield session
