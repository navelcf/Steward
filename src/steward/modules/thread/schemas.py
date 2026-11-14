# 依旧是出入参定义 / 接口契约

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# 新建会话；不传 title 就用默认值，由 model 层的 default 决定。
class ThreadCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)


# 改名；PATCH 只改这一个字段，所以设成必填（没传直接 422）。
class ThreadUpdateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


# 出参；故意不含 user_id —— 前端不需要，最小暴露。
# 有点过分谨慎了，到最后测试的时候，不会被我一个抓包全抓出来了吧？
class ThreadOut(BaseModel):
    id: str
    title: str
    active_workflow: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
    # 又是这个！应该到最后还是个过滤！
