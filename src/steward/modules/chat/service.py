from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID
# UUID:解析校验file_id

from fastapi import Request

from steward.core.config import settings
from steward.core.logging import get_logger
from steward.modules.file.service import ALLOWED_SUFFIXES, STORAGE_ROOT, TOKEN_FACTOR, extract_text

logger = get_logger(__name__)


# 业务异常；统一转成 SSE 的 error 事件，不让连接无声断掉。
class DocumentNotFoundError(Exception):  # 文件不存在
    pass


class DocumentTooLargeError(Exception):  # 文件太大
    pass


# SSE（Server-Sent Events）——单向长连接。服务器一直往外推，客户端只管收。轻，够用。
# SSE 事件格式：event: 和 data: 后各有一个空格，结尾两个换行，一个都不能少。
def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    # ensure_ascii=False：中文输出


# 按 file_id 在用户目录找回文件；校验 uuid 格式、唯一匹配、路径前缀、后缀白名单。
def resolve_document(file_id: str, user_id: int) -> Path:
    try:
        UUID(file_id)  # 格式闸
    except ValueError as exc:  # valueerror：类型对了，数值不对
        raise DocumentNotFoundError("文件不存在") from exc

    user_dir = (STORAGE_ROOT / str(user_id)).resolve()
    if not user_dir.is_relative_to(STORAGE_ROOT):  # 目录闸，理论上user_id是数据库自己填的，根本没法作妖啊
        raise DocumentNotFoundError("文件不存在")

    matches = [p for p in user_dir.glob(f"{file_id}.*") if p.is_file()]
    # `.glob("模式")`的意思是：去这个目录里，按通配符找匹配的项。
    # `p.is_file()`：只取文件，不取目录。
    if len(matches) != 1:  # 唯一匹配
        raise DocumentNotFoundError("文件不存在")

    target = matches[0].resolve()
    suffix = target.suffix.lower()
    if not target.is_relative_to(STORAGE_ROOT) or suffix not in ALLOWED_SUFFIXES:
        raise DocumentNotFoundError("文件不存在")
    return target


# 组装 prompt；带 file_id 时把文档全文塞进去，超上限先拒绝，别把钱烧在超长请求上。
def build_prompt(message: str, file_id: str | None, user_id: int) -> str:
    if file_id is None:
        return message

    path = resolve_document(file_id, user_id)
    text = extract_text(path, path.suffix.lower())
    if int(len(text) * TOKEN_FACTOR) > settings.llm.max_doc_tokens:
        raise DocumentTooLargeError("文档过长，请分段提问或加入知识库")

    return f"以下是文档内容：\n<document>\n{text}\n</document>\n\n用户问题：{message}"


# 异步生成器：产出一条条 SSE 文本块，StreamingResponse 边产边推。
async def event_stream(request: Request, message: str, file_id: str | None, user_id: int) -> AsyncGenerator[str, None]:
    try:
        prompt = build_prompt(message, file_id, user_id)
    except (DocumentNotFoundError, DocumentTooLargeError) as exc:
        yield _sse("error", {"message": str(exc)})
        yield _sse("done", {"ok": False})
        return

    model = request.app.state.chat_model
    try:
        async for chunk in model.astream(prompt):
            delta = chunk.content
            if isinstance(delta, str) and delta:  # isinstance(delta, str)判断是否为字符串
                yield _sse("message", {"delta": delta})
    except Exception:
        # 流已经开始了，没法再改 HTTP 状态码；只能补一个 error 事件告诉前端。
        logger.exception("模型流式生成失败", user_id=user_id)
        yield _sse("error", {"message": "生成失败，请稍后重试"})
        yield _sse("done", {"ok": False})
        return

    yield _sse("done", {"ok": True})
