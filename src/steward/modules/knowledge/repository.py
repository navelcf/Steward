from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from steward.modules.knowledge.models import Document, ParentChunk


# 只做 documents / parent_chunks 的数据访问；user_id 下推 WHERE。
class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_document(self, doc_id: str, user_id: int) -> Document | None:
        return await self.session.scalar(
            select(Document).where(Document.id == doc_id, Document.user_id == user_id)
        )

    async def get_by_hash(self, user_id: int, content_hash: str) -> Document | None:
        return await self.session.scalar(
            select(Document).where(
                Document.user_id == user_id,
                Document.content_hash == content_hash,
            )
        )

    async def list_documents(self, user_id: int, limit: int, offset: int) -> Sequence[Document]:
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(stmt)).all()

    async def add_document(self, row: Document) -> None:
        self.session.add(row)
        await self.session.flush()

    async def add_parents(self, rows: Sequence[ParentChunk]) -> None:
        self.session.add_all(list(rows))
        await self.session.flush()

    async def list_parents(self, doc_id: str, user_id: int) -> Sequence[ParentChunk]:
        stmt = (
            select(ParentChunk)
            .where(ParentChunk.doc_id == doc_id, ParentChunk.user_id == user_id)
            .order_by(ParentChunk.seq.asc())
        )
        return (await self.session.scalars(stmt)).all()

    async def delete_document(self, doc: Document) -> None:
        # parent_chunks 靠外键 CASCADE 删，不用手动清。
        await self.session.delete(doc)
        await self.session.flush()