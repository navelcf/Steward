from __future__ import annotations

from fastapi import FastAPI,Request
from pymilvus import DataType, Function, FunctionType, MilvusClient

from steward.core.config import settings
from steward.core.logging import get_logger

logger = get_logger(__name__)


# 建子块集合；已存在就跳过。字段与方案 7.4 一致，v3 下 VARCHAR 仍可用。
def ensure_collection(client: MilvusClient) -> None:
    name = settings.milvus.collection
    if client.has_collection(name):
        logger.info("Milvus 集合已存在", collection=name)
        return

    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    # enable_dynamic_field=False，是否允许动态字段
    schema.add_field("child_id", DataType.VARCHAR, is_primary=True, max_length=64)
    # 主键
    schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
    # 出自哪份文档。
    schema.add_field("parent_id", DataType.VARCHAR, max_length=64)
    # `parent_id`同父的多个子块靠它去重
    schema.add_field("user_id", DataType.INT64)
    # 隔离
    schema.add_field("section_path", DataType.VARCHAR, max_length=500)
    # `section_path`在文档哪一节（「第 3.2 节」）。引用时能标到章节
    # `section_path` 具体长什么样，取决于切分器怎么填。比如 `"# 公司概况 > ## 主营业务 > ### 成本结构"`


    # content 开中文分词：BM25 的稀疏向量由它自动生成，不用自己算。
    schema.add_field(
        "content",
        DataType.VARCHAR,
        max_length=4096,
        enable_analyzer=True,# 允许分词
        analyzer_params={"type": "chinese"},# # 指定分词方式，这里选择中文分词
    )
    schema.add_field("raw_content", DataType.VARCHAR, max_length=4096)
    # 切块
    # 「small-to-big」或「parent-child retrieval」, 小块检索、大块返回。
    # 这里是父块
    # `raw_content` 只用来读，不做检索，不需要分词。
    schema.add_field("dense", DataType.FLOAT_VECTOR, dim=settings.milvus.dim)
    # 稠密向量
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
    # 稀疏向量

    # 添加BM25函数，可以自动把原始文档转BM25向量存储
    schema.add_function(
        Function(
            name="bm25",
            function_type=FunctionType.BM25,
            input_field_names=["content"],
            output_field_names=["sparse"],
        )
    )

    index_params = client.prepare_index_params()
    index_params.add_index("dense", index_type="AUTOINDEX", metric_type="COSINE")#相似度计算
    index_params.add_index("sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
    # 稀疏向量，采用倒排索引， # 相似度计算方式，支持 BM25、IP
    client.create_collection(collection_name=name, schema=schema, index_params=index_params)
    logger.info("Milvus 集合已创建", collection=name, dim=settings.milvus.dim)


# 启动时连一次；失败只记日志，不阻塞服务（Milvus 只服务 RAG，不该拖垮 chat）。
def init_milvus(app: FastAPI) -> None:
    try:
        # 这个构造函数会立即握手，连不上直接抛 MilvusException。
        client = MilvusClient(uri=settings.milvus.uri, timeout=5)
        ensure_collection(client)
    except Exception:
        logger.exception("Milvus 初始化失败，RAG 功能将不可用", uri=settings.milvus.uri)
        app.state.milvus = None
        return

    app.state.milvus = client
    logger.info(
        "Milvus 客户端就绪",
        uri=settings.milvus.uri,
        collection=settings.milvus.collection,
        dim=settings.milvus.dim,
    )


# 关闭时调用；没初始化成功就跳过。
def close_milvus(app: FastAPI) -> None:
    client: MilvusClient | None = getattr(app.state, "milvus", None)
    if client is None:
        return
    client.close()
    logger.info("Milvus 客户端已关闭")


# FastAPI 依赖：取 lifespan 建好的客户端；没成功就是 None，由调用方转 503。
def get_milvus(request: Request) -> MilvusClient | None:
    return getattr(request.app.state, "milvus", None)