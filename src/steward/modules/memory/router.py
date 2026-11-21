# 整个文件就这些，响应模型和路由放在同一个文件里（只有一个响应类，不值得单开 schemas.py）
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.auth.models import User
from steward.modules.memory.repository import MemoryRepository

router = APIRouter(prefix="/api/v1", tags=["memory"])


# 记忆出参；不暴露 user_id（最小暴露）。
class MemoryOut(BaseModel):
    id: str
    kind: str
    title: str
    content: str
    importance: int
    version: int
    source_run_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# 列自己的长期记忆；给验收和调试用。
@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MemoryOut]:
    rows = await MemoryRepository(session).list_all(current_user.id, limit)
    return [MemoryOut.model_validate(row) for row in rows]
