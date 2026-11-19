from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pymilvus import AnnSearchRequest, DataType, Function, FunctionType, MilvusClient, RRFRanker

from steward.core.config import settings

# 临时集合：维度小、名字带 probe，测完就删，不碰 child_chunks_v1。
PROBE = "probe_v1"
DIM = 8


def build_probe(client: MilvusClient) -> None:
    if client.has_collection(PROBE):
        client.drop_collection(PROBE)

    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("child_id", DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
    schema.add_field("parent_id", DataType.VARCHAR, max_length=64)
    schema.add_field("user_id", DataType.INT64)
    schema.add_field("section_path", DataType.VARCHAR, max_length=500)
    schema.add_field(
        "content",
        DataType.VARCHAR,
        max_length=4096,
        enable_analyzer=True,
        analyzer_params={"type": "chinese"},
    )
    schema.add_field("raw_content", DataType.VARCHAR, max_length=4096)
    schema.add_field("dense", DataType.FLOAT_VECTOR, dim=DIM)
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_function(
        Function(
            name="bm25",
            function_type=FunctionType.BM25,
            input_field_names=["content"],
            output_field_names=["sparse"],
        )
    )
    index_params = client.prepare_index_params()
    index_params.add_index("dense", index_type="AUTOINDEX", metric_type="COSINE")
    index_params.add_index("sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
    client.create_collection(collection_name=PROBE, schema=schema, index_params=index_params)
    print("集合已建:", PROBE)


def main() -> None:
    client = MilvusClient(uri=settings.milvus.uri, timeout=5)
    print("server version =", client.get_server_version())
    build_probe(client)

    rows = [
        {
            "child_id": "c1", "doc_id": "d1", "parent_id": "p1", "user_id": 4,
            "section_path": "第3章 > 3.2 责任免除", "content": "责任免除 战争 核辐射 不赔",
            "raw_content": "战争、核辐射等情形不承担赔偿责任。", "dense": [0.1] * DIM,
        },
        {
            "child_id": "c2", "doc_id": "d1", "parent_id": "p1", "user_id": 4,
            "section_path": "第3章 > 3.2 责任免除", "content": "等待期 九十天 既往症",
            "raw_content": "首次投保九十天内因既往症出险不赔。", "dense": [0.2] * DIM,
        },
        {
            "child_id": "c3", "doc_id": "d2", "parent_id": "p2", "user_id": 9,
            "section_path": "第1章 > 1.1 保障范围", "content": "住院 医疗 报销 比例",
            "raw_content": "住院医疗费用按约定比例报销。", "dense": [0.3] * DIM,
        },
    ]
    print("插入 =", client.insert(collection_name=PROBE, data=rows))
    client.flush(PROBE)

    expr = "user_id == 4"
    dense_req = AnnSearchRequest([[0.1] * DIM], "dense", {"metric_type": "COSINE"}, limit=5, expr=expr)
    sparse_req = AnnSearchRequest(["责任免除"], "sparse", {"metric_type": "BM25"}, limit=5, expr=expr)
    hits = client.hybrid_search(
        collection_name=PROBE,
        reqs=[dense_req, sparse_req],
        ranker=RRFRanker(60),
        limit=5,
        output_fields=["child_id", "parent_id", "section_path"],
    )[0]
    print("混合检索(仅 user 4) =", [(h["child_id"], round(h["distance"], 4), h["entity"]["parent_id"]) for h in hits])

    bm25 = client.search(
        collection_name=PROBE,
        data=["既往症 等待期"],
        anns_field="sparse",
        search_params={"metric_type": "BM25"},
        limit=3,
        output_fields=["child_id", "raw_content"],
    )[0]
    print("纯 BM25 =", [(h["child_id"], round(h["distance"], 3)) for h in bm25])

    other = client.search(
        collection_name=PROBE,
        data=["责任免除"],
        anns_field="sparse",
        search_params={"metric_type": "BM25"},
        limit=5,
        filter="user_id == 9",
        output_fields=["child_id"],
    )[0]
    print("租户隔离(user 9) =", [h["child_id"] for h in other])

    client.drop_collection(PROBE)
    print("临时集合已删, 剩余 =", client.list_collections())
    client.close()


if __name__ == "__main__":
    main()