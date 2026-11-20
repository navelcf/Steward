from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# 文档出参；不暴露 storage_path（服务端绝对路径）。
class DocumentOut(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    version: int
    page_count: int | None
    char_count: int | None
    is_indexed: bool
    parser: str | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# 检索入参；top_k 是召回数，不是返回数（返回会按 parent_id 去重）。
class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    # 防超长把 embedding API 打爆（`text-embedding-v4` 单条也有上限）
    # 问题
    top_k: int = Field(default=20, ge=1, le=50)
    # 用户传的 `top_k=20` 从 Milvus 召回 20 个子块
    # 去重后N 个父块（N ≤ 20，可能远小于）
    # 上限，防「一次拉 10000 条」把 Milvus 压垮
    # 召 50 个已经很多了。
    # 再往上，纯属「拿噪声喂模型」——`raw_content` 每个 1500 字，召 100 个就是 15 万字，直接爆 prompt。
    doc_ids: list[str] | None = Field(default=None, description="限定文档范围，不传就是全部")
    # 限定文档范围
    # `[]`（空列表）限定了「零份文档」→ 结果必然是空



# 检索命中；一条对应一个父块。
class SearchHitOut(BaseModel):
    child_id: str# 调试 / 溯源知道是哪一小段命中的
    doc_id: str# 前端显示「出自《茅台年报》」
    parent_id: str# 内部 / 前端去重键、跳转锚点
    section_path: str# `section_path`前端显示「第 3.2 节 成本结构」
    raw_content: str# 模型拼进 prompt 的那段 1500 字
    score: float # `score`前端 / 调试排序、展示置信度
    # `score` 是 RRF 融合后的分数，大概在 `0.01 ~ 0.05` 之间。
    # 它不是：- 余弦相似度（0~1）- 百分比- 归一化
    # 它只能用来「比大小、排序」，绝对值不可解释。
    # 所以前端别显示成「相似度 3.28%」—— 用户会困惑「3% 也叫相关？」
    # 要么不显示，要么自己归一化成「第 1 名 100%、第 2 名 80%」这种相对值。


# 出参
class SearchOut(BaseModel):
    query: str
    hits: list[SearchHitOut]