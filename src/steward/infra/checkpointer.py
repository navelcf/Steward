from __future__ import annotations

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from steward.core.config import settings
from steward.core.logging import get_logger

logger = get_logger(__name__)


# 在 lifespan 里创建；模块级不建连接池。
async def init_checkpointer(app: FastAPI) -> None:
    pool = AsyncConnectionPool(# 连接池对象
        conninfo=settings.db.checkpoint_url,# 数据库连接信息
        min_size=1,# 最小连接数
        max_size=5,# 最大连接数
        kwargs={
            "autocommit": True,
            # LangGraph 写 checkpoint 不走我的事务，它自己控制提交时机
            "prepare_threshold": 0,
            # 关掉 prepared statement 缓存。连接池会复用连接，复用时会撞上上一个客户端的预编译语句
            "row_factory": dict_row,
            # 让查询结果返回 dict（按列名取值），而不是 tuple（按位置取值）。LangGraph 内部按列名读
        },
        open=False,# 先构造对象，别急着连接
    )
    # 失败时先把池关掉，别留下悬空资源；和 infra/database.py 的写法一致。
    try:
        await pool.open()# 开始按 `min_size` 去连数据库（发起了，但不定连上）
        await pool.wait()# 等到池里至少有 `min_size` 条真的连上了才返回
        # `await pool.wait()` 是等最小连接数（1 条）真正连上。
        # `open()` 只表示 “开始连”，`wait()` 才表示 “连好了”。
        saver = AsyncPostgresSaver(pool)# 创建 saver 对象，`AsyncPostgresSaver(pool)` 传的是池，不是连接
        # self.conn = conn，就这一步，这个玩意是langgraph导入的，根本上为了checkpoint而生，单纯理解为建一个标准对象
        await saver.setup()# `setup()` 建了四张表
    except Exception:
        await pool.close()
        raise

    app.state.checkpoint_pool = pool
    app.state.checkpointer = saver
    logger.info(
        "Checkpointer 就绪",
        host=settings.db.host,
        port=settings.db.port,
        database=settings.db.name,
        pool_max_size=5,
    )


# 关闭时调用；没初始化过就直接返回，重复调用安全。
async def close_checkpointer(app: FastAPI) -> None:
    pool: AsyncConnectionPool | None = getattr(app.state, "checkpoint_pool", None)
    if pool is None:
        logger.warning("Checkpointer 未初始化，跳过关闭")
        return
    await pool.close()
    logger.info("Checkpointer 连接池已关闭")