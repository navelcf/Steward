from __future__ import annotations

from collections.abc import Sequence

from dashscope import TextEmbedding

from steward.core.config import settings
from steward.core.logging import get_logger

logger = get_logger(__name__)

# text-embedding-v4 单次最多 10 条；超过要分批，不然直接 400。
BATCH_SIZE = 10


# embedding 调用失败；上层转 502，不把百炼的原始报文透给用户。
# `dashscope` 会抛自己的异常（`DashScopeAPIError` 等），上层不该知道这个库的名字。
# 说实话为什么要考虑这些，我觉得太谨慎了
class EmbeddingError(Exception):
    pass


# 批量向量化：每批 10 条，按 text_index 还原顺序。
def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []

    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = list(texts[start : start + BATCH_SIZE])
        resp = TextEmbedding.call(
            model=settings.embedding.model,
            input=batch,
            dimension=settings.milvus.dim,
            api_key=settings.embedding.api_key,
        )
        if resp.status_code != 200:
            logger.error("embedding 调用失败", code=resp.code, message=resp.message, batch=len(batch))
            raise EmbeddingError(f"向量化失败: {resp.code}")

        # 批量返回不保证顺序，按 text_index 排回原序。
        items = sorted(resp.output["embeddings"], key=lambda item: item["text_index"])
        vectors.extend(item["embedding"] for item in items)
        # 一个一个塞进去，不是整个塞进去

    logger.info("embedding 完成", texts=len(texts), vectors=len(vectors), dim=settings.milvus.dim)
    return vectors