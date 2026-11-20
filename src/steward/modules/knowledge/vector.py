# 将数据传入 Milvus
# Milvus 的三个读、写、删、搜入口
from __future__ import annotations

from collections.abc import Sequence

from pymilvus import AnnSearchRequest, MilvusClient, RRFRanker

from steward.core.config import settings
from steward.core.logging import get_logger

logger = get_logger(__name__)


# 把切好的子块塞进 Milvus
# 批量写子块；sparse 不传，由 BM25 Function 自动生成。
def insert_children(client: MilvusClient, rows: Sequence[dict]) -> int:
    if not rows:
        return 0
    result = client.insert(collection_name=settings.milvus.collection, data=list(rows))
    client.flush(settings.milvus.collection)
    return int(result.get("insert_count", 0))


# 删：按文档 ID 清掉它的所有子块
# 删文档时清它的全部子块；user_id 一起带上，防越权删。
def delete_by_doc(client: MilvusClient, doc_id: str, user_id: int) -> None:
    client.delete(
        collection_name=settings.milvus.collection,
        filter=f'doc_id == "{doc_id}" and user_id == {user_id}',
        # `client.delete` 是同步可见的（Milvus 的删除标记是立即可见的），不用 `flush`
    )


# 搜：双路检索 + 融合 + 去重
# 混合检索：dense + sparse 双路，RRF 融合，按 parent_id 去重。
def hybrid_search(
    client: MilvusClient,
    query_text: str,
    query_vector: list[float],
    user_id: int,
    top_k: int,
    doc_ids: list[str] | None = None,
) -> list[dict]:
    # 租户过滤必须下推到检索层（方案 4.6 / L550）。
    expr = f"user_id == {user_id}"
    if doc_ids:
        quoted = ", ".join(f'"{item}"' for item in doc_ids)
        # ["a3f8", "c7b2"]   →   '"a3f8", "c7b2"'
        expr += f" and doc_id in [{quoted}]"
        # `and` 是 Milvus 表达式的语法（不是 Python 的 `and` 关键字）。
        #  Milvus 支持 `and` / `or` / `in` / `like`

    dense_req = AnnSearchRequest(
        # radius：余弦相似度低于它的命中直接丢弃，这就是「查不到」能真的为空的原因。
        [query_vector],
        "dense",
        {"metric_type": "COSINE", "params": {"radius": settings.rag.min_score}},
        limit=top_k,
        expr=expr,
        # `data`要搜的东西稠密传 `[向量]`，稀疏传 `[文本]`
        # [query_vector]       # 而不是 query_vector
        # 因为 Milvus 支持「一次搜多个查询」：
        # data=[q1_vec, q2_vec]    # 一次搜两个问题，返回两组结果
        # 传的是 `[query_vector]`，一个已经在 Python 里算好的 1024 维数组。
        # `anns_field`在哪个字段上搜`"dense"` 或 `"sparse"`
        # `param`搜索参数`metric_type` 必须和建索引时一致（`COSINE` / `BM25`）
        # `limit`这一路要几条候选传 `top_k`，两路各取 top_k 条
        # 把 `user_id == 4` 下推给 Milvus，不拉全库回来再过滤
    )
    sparse_req = AnnSearchRequest(  # 稀疏向量传 [文本]，milvus自动给你算好了
        [query_text], "sparse", {"metric_type": "BM25"}, limit=top_k, expr=expr
    )
    hits = client.hybrid_search(
        collection_name=settings.milvus.collection,
        reqs=[dense_req, sparse_req],
        ranker=RRFRanker(60),
        limit=top_k,  # 这里的 limit 是两路检索结果合起来之后再取 top_k
        output_fields=["child_id", "doc_id", "parent_id", "section_path", "raw_content"],
    )[0]
    # # 为什么是 `[0]`
    # `hybrid_search` 返回的是 `list[list[Hit]]`—— 外层是「每个查询」，内层是「每个命中」。
    # 主键取 hit["child_id"]，不是 hit["id"]。
    # 分数在 hit["distance"]，RRF 融合后是个很小的数（0.03 量级），不是百分比。
    # 其他字段在 hit["entity"]
    #     hit = {
    #     "child_id": "c1",              # ← 主键，直接在顶层，key 就是字段名
    #     "distance": 0.0328,            # ← 分数，key 叫 distance
    #     "entity": {                    # ← 其他 output_fields 全装这里
    #         "doc_id": "d1",
    #         "parent_id": "p1",
    #         "section_path": "第3章 > 3.2 责任免除",
    #         "raw_content": "战争、核辐射等情形不承担赔偿责任。",
    #     },
    # }

    # 假设 `hits`（已经按融合分降序）是：
    # 同一父块的多个子块只留最高分那条，顺序按融合分数。
    # P1（分 0.033）  ← 高粱子块
    # P2（分 0.028）  ← 成本总体子块
    # P1（分 0.025）  ← 小麦子块
    # P3（分 0.020）  ← 产量总体子块
    # P1（分 0.015）  ← 原材料子块

    seen: set[str] = set()  # 集合，O(1)，哈希直查
    results: list[dict] = []  # 结果列表
    for hit in hits:
        entity = hit["entity"]
        parent_id = entity["parent_id"]
        if parent_id in seen:
            continue
        seen.add(parent_id)
        results.append(
            {
                "child_id": hit["child_id"],
                "doc_id": entity["doc_id"],
                "parent_id": parent_id,
                "section_path": entity["section_path"],
                "raw_content": entity["raw_content"],
                "score": hit["distance"],
            }
        )
    return results
