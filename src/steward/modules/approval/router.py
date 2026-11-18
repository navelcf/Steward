from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langgraph.types import Command  # 终于来command了
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.common.sse import sse_event
from steward.infra.database import get_session
from steward.modules.approval.deps import get_pending_approval
from steward.modules.approval.models import Approval
from steward.modules.approval.schemas import ApprovalOut, ApprovalStatus, DecisionIn
from steward.modules.approval.service import ApprovalConflictError, ApprovalService
from steward.modules.auth.models import User
from steward.modules.chat.service import event_stream

router = APIRouter(prefix="/api/v1/approvals", tags=["approval"])


# 把 DecisionIn 翻成 LangGraph 认的 decision 形状（实测四种，见 0.3）。
# edit 需要原工具名：改名等于换成另一个操作，不允许。
def build_decision(body: DecisionIn, tool_name: str) -> dict[str, object]:
    if body.decision == "approve":
        return {"type": "approve"}
    if body.decision == "reject":
        return {"type": "reject", "message": body.note or "用户拒绝"}
    return {
        "type": "edit",
        "edited_action": {"name": tool_name, "args": body.edited_args or {}},
    }


# 待确认卡片列表；status 不传就是全部。归属过滤在 repository 里下推。
@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalOut]:
    rows = await ApprovalService(session).list_approvals(current_user.id, status_filter, limit, offset)
    return [ApprovalOut.model_validate(row) for row in rows]


# 决策 + 恢复：先 CAS 落状态，再用 interrupt_id 接回原 thread 继续流式输出。
# 404 / 409 由依赖层在响应头之前抛；CAS 竞态失败只能推 error 事件。
@router.post("/{approval_id}/decide", response_class=EventSourceResponse)
# EventSourceResponse：「把异步生成器逐条变成 SSE 帧并写出去」的响应类
# 1. 设置响应头：`Content-Type: text/event-stream; charset=utf-8`
# 2. 设置 `Cache-Control: no-cache`（防止代理和浏览器缓存流）
# 3. 迭代你的生成器，每拿到一个 `ServerSentEvent`，序列化成
async def decide(
    approval_id: str,
    body: DecisionIn,
    request: Request,
    approval: Approval = Depends(get_pending_approval),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[ServerSentEvent, None]:
    try:
        await ApprovalService(session).decide(approval_id, current_user.id, body)
    except ApprovalConflictError:
        # 依赖层查到 pending，但这一瞬间被别人抢了；响应头已发，只能发事件。
        yield sse_event("error", {"message": "审批已处理"})
        yield sse_event("done", {"ok": False})
        return

    # 统一带 interrupt_id：单卡多卡都能用，不用判 pending 张数（实测见 0.3）。
    resume = Command(resume={approval.interrupt_id: build_decision(body, approval.tool_name)})
    # 这是 `per_call` 格式：`{interrupt_id: decision}`
    async for event in event_stream(
        request,
        approval.thread_id,
        "",  # resume 轮次没有新用户消息
        None,  # 也不带文档
        current_user.id,
        resume=resume,
        note_id=approval.id,
    ):
        yield event
