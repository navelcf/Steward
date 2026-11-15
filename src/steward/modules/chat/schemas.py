from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


# 流式对话入参；file_id 可选，带了就走「全文读」。
class ChatIn(BaseModel):
    thread_id: str = Field(min_length=36, max_length=36)
    message: str = Field(min_length=1, max_length=4000)
    # 用户输入必须限长，其余走文件；file_id 可选，带了就走「全文读」。
    # 但是按我自己的想法，包括我使用其他agent或者llm的时候，我也喜欢复制过去直接当message
    # 这个4000怕是我自己都觉得不够用，我个人认为完全不用限长。
    file_id: str | None = None


# 历史消息出参；不含 user_id（前端不需要，最小暴露）。
class MessageOut(BaseModel):
    id: int
    thread_id: str
    role: str
    content: str
    sources: list[dict] | None
    run_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# 历史列表；total 给分页用，items 按时间升序。
class MessageListOut(BaseModel):
    items: list[MessageOut]  # 按时间升序，那就是按时间给模型看历史记录，确实应该升序，
    total: int  # 总数，分页用
