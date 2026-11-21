from __future__ import annotations

from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.exc import IntegrityError

# 它是 SQLAlchemy 的一个异常类，专门表示 “数据库的完整性约束被违反了”
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from steward.core.logging import get_logger
from steward.modules.memory.extractor import extract_memory
from steward.modules.memory.models import Memory
from steward.modules.memory.repository import MemoryRepository

logger = get_logger(__name__)

# 召回条数与最低重要度；条数少，3 条 3 分以上就够。
RECALL_LIMIT = 3
RECALL_MIN_IMPORTANCE = 3


class MemoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MemoryRepository(session)

    # 新会话首轮调用；返回给 prompt 用的一行行文本。
    async def recall_lines(self, user_id: int) -> list[str]:
        rows = await self.repo.list_for_recall(user_id, RECALL_LIMIT, RECALL_MIN_IMPORTANCE)
        return [f"- [{row.kind}] {row.title}：{row.content}" for row in rows]

    # 按去重键写一条：存在就更新内容并 version+1，不存在就插入。
    async def save(self, user_id: int, data: dict, run_id: str | None) -> Memory | None:
        existing = await self.repo.get_by_key(user_id, data["kind"], data["title"])
        if existing is not None:
            existing.content = data["content"]
            existing.importance = data["importance"]
            existing.source_run_id = run_id
            existing.version += 1
            await self.session.commit()
            logger.info("记忆已更新", memory_id=existing.id, version=existing.version)
            return existing

        row = Memory(
            id=str(uuid4()),
            user_id=user_id,
            kind=data["kind"],
            title=data["title"],
            content=data["content"],
            source_run_id=run_id,
            importance=data["importance"],
        )
        try:
            await self.repo.add(row)
            await self.session.commit()
        except IntegrityError:
            # 并发下另一个请求先插了同键；回滚并当作已存在处理。
            await self.session.rollback()
            logger.warning("记忆并发写入冲突，已跳过", title=data["title"][:30])
            return None
        logger.info("记忆已写入", memory_id=row.id, kind=row.kind, importance=row.importance)
        return row


# 后台任务：自己开 session，抽完就写。调用方 await 会阻塞，所以必须 create_task。
# 为什么这里必须自己开，而不是用 `chat/service.py` 那个 session：
# 这个函数是 `create_task` 起的，跑在另一个协程里。
# 那时候请求级的session早就关了`chat/service.py` 的段 2 结束时关的）。
# 拿那个 session 会报 `Session is closed`
async def write_memory_in_background(
    factory: async_sessionmaker[AsyncSession],
    model: BaseChatModel,
    user_id: int,
    run_id: str | None,
    user_text: str,
    answer: str,
) -> None:
    data = await extract_memory(model, user_text, answer)
    if data is None:
        return
    try:
        async with factory() as session:
            await MemoryService(session).save(user_id, data, run_id)
    except Exception:
        logger.exception("记忆落库失败", user_id=user_id, title=data.get("title", "")[:30])
