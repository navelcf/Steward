from __future__ import annotations

from pymilvus import MilvusClient
from sqlalchemy.ext.asyncio import AsyncSession

from steward.core.logging import get_logger
from steward.infra.embedding import embed_texts
from steward.modules.knowledge.repository import KnowledgeRepository
from steward.modules.knowledge.vector import hybrid_search
from steward.core.config import settings

logger = get_logger(__name__)


# 检索 -> 父块回查 -> 分配引用编号。Agent 工具和调试接口共用这一条路径。
async def retrieve_sources(
    session: AsyncSession,
    milvus: MilvusClient,
    user_id: int,
    query: str,
    top_k: int = 20,
    final_k: int = 6,
    doc_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    vector = embed_texts([query])[0]
    hits = hybrid_search(milvus, query, vector, user_id, top_k, doc_ids)


    dense_echo = milvus.search(
        collection_name=settings.milvus.collection,
        data=[vector],
        anns_field="dense",
        search_params={"metric_type": "COSINE", "params": {"radius": settings.rag.min_score}},
        limit=1,
        filter=f"user_id == {user_id}",
        output_fields=["child_id"],
    )
    if not dense_echo[0]:
        logger.info("检索判为无答案", query_len=len(query))
        return []


    if not hits:
        return []

    # hybrid_search 已按 parent_id 去重并保序；这里只截断到 final_k。
    ordered = [hit["parent_id"] for hit in hits][:final_k]
    rows = await KnowledgeRepository(session).batch_get_with_filename(ordered, user_id)
    by_id = {chunk.id: (chunk, filename) for chunk, filename in rows}

    sources: list[dict[str, str]] = []
    for parent_id in ordered:
        pair = by_id.get(parent_id)
        if pair is None:
            # 父块被删：跳过并记告警，不留悬空引用（方案 7.9）。
            logger.warning("父块缺失，跳过引用", parent_id=parent_id, user_id=user_id)
            continue
        chunk, filename = pair
        sources.append(
            {
                # 用 parent_id 前 8 位：多次检索不撞号，同一父块编号稳定。
                "source_id": f"ref-{chunk.id[:8]}",
                "doc_id": chunk.doc_id,
                "clause_name": filename,
                "section_path": chunk.section_path,
                "content": chunk.content,
            }
        )
    logger.info("检索完成", query_len=len(query), hits=len(hits), sources=len(sources))
    return sources
