from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse  # 流式响应

from steward.common.deps import get_current_user
from steward.modules.auth.models import User
from steward.modules.chat.schemas import ChatIn
from steward.modules.chat.service import event_stream

# prefix 写全；main.py 里 include_router 不要再叠 prefix。
router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# 流式对话；必须登录，生成器交给 StreamingResponse 边产边推。
@router.post("/stream")
async def chat_stream(
    body: ChatIn,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    return StreamingResponse(
        event_stream(request, body.message, body.file_id, current_user.id),
        media_type="text/event-stream",
        # 它最终变成响应头里的 `Content-Type: text/event-stream`。
        # 作用：告诉浏览器「我发的不是 JSON，是一串 SSE 事件」。
        # `text/event-stream` 是 SSE 的官方 MIME 类型，写错了前端就按别的格式解析。
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        # `Cache-Control: no-cache`告诉浏览器和中间代理：别缓存这个响应
        # 因为 SSE 是一个**持续变化**的流。缓存了，第二次请求可能拿到第一次的旧内容。
        # `X-Accel-Buffering: no` 就是告诉 Nginx：别缓冲，来一块转一块。
        # 它真正的用处是 P1：你把服务部署到云主机、前面挂 Nginx 之后，它就生效了
    )
