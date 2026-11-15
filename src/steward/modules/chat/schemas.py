from __future__ import annotations

from pydantic import BaseModel, Field


# 流式对话入参；file_id 可选，带了就走「全文读」。
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    # 用户输入必须限长，其余走文件；file_id 可选，带了就走「全文读」。
    # 但是按我自己的想法，包括我使用其他agent或者llm的时候，我也喜欢复制过去直接当message
    # 这个4000怕是我自己都觉得不够用，我个人认为完全不用限长。
    file_id: str | None = None
