# _sse 是 chat/service.py 的私有函数，跨模块 import 私有名不规范；复制一份又会漂移
from __future__ import annotations

import json

from fastapi.sse import ServerSentEvent


# 构造一条 SSE 事件；event 名与 data 的 JSON 序列化只写这一处。
# raw_data 传已序列化的字符串，避免 ServerSentEvent 自动 JSON 编码改契约（中文会被转义）。
def sse_event(event: str, data: dict[str, object]) -> ServerSentEvent:
    return ServerSentEvent(
        raw_data=json.dumps(data, ensure_ascii=False),
        event=event,
    )
