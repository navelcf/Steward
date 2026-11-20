from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pymilvus import MilvusClient
from sqlalchemy.ext.asyncio import AsyncSession

from steward.common.deps import get_current_user
from steward.infra.database import get_session
from steward.infra.milvus import get_milvus
from steward.modules.auth.models import User
from steward.modules.knowledge.schemas import DocumentOut, SearchHitOut, SearchIn, SearchOut
from steward.modules.knowledge.service import (
    DocumentTooLargeError,
    KnowledgeService,
    MilvusNotReadyError,
    UnsupportedFormatError,
)

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


# 上传并同步入库；P0 不做后台任务，大文件会阻塞这个请求（见坑表 8）。
@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    milvus: MilvusClient | None = Depends(get_milvus),
) -> DocumentOut:
    data = await file.read()
    try:
        doc = await KnowledgeService(session, milvus).ingest(
            current_user.id,
            file.filename or "unknown",
            file.content_type or "",
            data,
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from exc
    except UnsupportedFormatError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except MilvusNotReadyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return DocumentOut.model_validate(doc)


# 列自己的文档；按创建时间倒序。
@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    milvus: MilvusClient | None = Depends(get_milvus),
) -> list[DocumentOut]:
    rows = await KnowledgeService(session, milvus).list_documents(current_user.id, limit, offset)
    return [DocumentOut.model_validate(row) for row in rows]


# 删除文档；先清 Milvus 子块，再删 PG（外键级联清父块）。
@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    milvus: MilvusClient | None = Depends(get_milvus),
) -> None:
    deleted = await KnowledgeService(session, milvus).delete_document(doc_id, current_user.id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")


# 混合检索；返回父块级结果，已按 parent_id 去重。
@router.post("/search", response_model=SearchOut)
async def search(
    body: SearchIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    milvus: MilvusClient | None = Depends(get_milvus),
) -> SearchOut:
    try:
        hits = await KnowledgeService(session, milvus).search(
            current_user.id, body.query, body.top_k, body.doc_ids
        )
    except MilvusNotReadyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return SearchOut(query=body.query, hits=[SearchHitOut(**hit) for hit in hits])