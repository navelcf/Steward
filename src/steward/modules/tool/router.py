from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.modules.auth.models import User
from steward.modules.tool.repository import ToolRepository
from steward.modules.tool.schemas import PolicyUpdateIn, ToolOut

router = APIRouter(prefix="/api/v1/tools", tags=["tool"])


# 列出全部工具；登录即可看，P2 再按角色收敛成管理员可见。
@router.get("", response_model=list[ToolOut])
async def list_tools(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ToolOut]:
    del current_user# 删除这个变量，不能没有，不然无法鉴权
    rows = await ToolRepository(session).list_all()
    return [ToolOut.model_validate(row) for row in rows]
    # model_validate:按 `ToolOut` 声明过的字段名去 `getattr` 取


# 改策略；工具名不存在一律 404，不区分「不存在」和「没权限」。
# 这种其实我认为考虑地太细了
@router.put("/{name}/policy", response_model=ToolOut)
async def update_policy(
    name: str,
    body: PolicyUpdateIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ToolOut:
    del current_user# 同理
    repo = ToolRepository(session)
    row = await repo.get_by_name(name)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工具不存在")
    updated = await repo.set_policy(row, body.policy)
    await session.commit()
    return ToolOut.model_validate(updated)