from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from steward.common.deps import get_current_user
from steward.modules.auth.models import User
from steward.modules.chat.deps import get_owned_thread
from steward.modules.chat.schemas import ChatIn
from steward.modules.chat.service import event_stream
from steward.modules.thread.models import ChatThread

# prefix 写全；main.py 里 include_router 不要再叠 prefix。
router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# 流式对话；必须登录 + 会话归属校验（依赖层，404 赶得上响应头）。
# 不标 response_model：路径函数是异步生成器，response_class 负责序列化。
@router.post("/stream", response_class=EventSourceResponse)
async def chat_stream(
    body: ChatIn,
    request: Request,
    thread: ChatThread = Depends(get_owned_thread),
    current_user: User = Depends(get_current_user),
) -> AsyncGenerator[ServerSentEvent, None]:
    del thread
    async for event in event_stream(request, body.thread_id, body.message, body.file_id, current_user.id):
        yield event
