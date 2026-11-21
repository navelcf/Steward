from __future__ import annotations

import hashlib

# Python 标准库，提供各种哈希算法：`md5` / `sha1` / `sha256`
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from pymilvus import MilvusClient

from steward.core.logging import get_logger
from steward.infra.embedding import embed_texts
from steward.modules.file.service import STORAGE_ROOT, TOKEN_FACTOR
from steward.modules.knowledge.models import Document, ParentChunk
from steward.modules.knowledge.parser import parse_document, split_children, split_parents
from steward.modules.knowledge.repository import KnowledgeRepository
from steward.modules.knowledge.vector import delete_by_doc, hybrid_search, insert_children

logger = get_logger(__name__)

# 文档根目录；复用 storage/，已被 .gitignore 忽略。
DOCUMENTS_ROOT = (STORAGE_ROOT / "documents").resolve()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class DocumentTooLargeError(Exception):
    pass


class UnsupportedFormatError(Exception):
    pass


# Milvus 未就绪（启动时连失败）；router 转 503。
class MilvusNotReadyError(Exception):
    pass


class KnowledgeService:
    def __init__(self, session: AsyncSession, milvus: MilvusClient | None) -> None:
        self.session = session
        self.milvus = milvus
        self.repo = KnowledgeRepository(session)

    # 上传 -> 解析 -> 切片 -> embedding -> 写 PG 与 Milvus，一步同步做完。
    async def ingest(
        self,
        user_id: int,
        filename: str,
        mime_type: str,
        data: bytes,  # 上传的文件二进制
    ) -> Document:
        if len(data) > MAX_UPLOAD_BYTES:
            raise DocumentTooLargeError("文件超过 20MB")
        if self.milvus is None:
            raise MilvusNotReadyError("Milvus 未就绪")

        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".docx", ".md", ".txt"}:
            raise UnsupportedFormatError(f"不支持的格式: {suffix}")

        content_hash = hashlib.sha256(data).hexdigest()
        # hexdigest()：把 hash 对象转成「十六进制字符串」
        existing = await self.repo.get_by_hash(user_id, content_hash)
        if existing is not None:
            # 内容没变就不重复入库（方案 4.3 的唯一约束意图）。
            logger.info("文档已存在，跳过", doc_id=existing.id, filename=filename)
            return existing

        # 写盘
        doc_id = str(uuid4())
        target_dir = (DOCUMENTS_ROOT / str(user_id)).resolve()
        if not target_dir.is_relative_to(DOCUMENTS_ROOT):
            raise UnsupportedFormatError("存储路径非法")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = (target_dir / f"{doc_id}{suffix}").resolve()
        target.write_bytes(data)

        # 写 PG
        # 落一条 `parsing` 记录
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            content_hash=content_hash,
            storage_path=str(target),
            status="parsing",
            version=1,
            is_indexed=False,
        )
        await self.repo.add_document(doc)

        try:  # 解析 + 切块
            parsed = parse_document(target, suffix)
            parents = split_parents(parsed.text)
            children = split_children(parents)
            if not children:
                raise UnsupportedFormatError("解析后没有可用文本")

            vectors = embed_texts([child.content for child in children])
            # 批量 embeddin

            parent_rows: list[ParentChunk] = []
            # 造父块行，算确定性 ID
            for seq, parent in enumerate(parents):
                parent_id = hashlib.sha1(f"{doc_id}{parent.section_path}{seq}".encode("utf-8")).hexdigest()[:16]
                parent_rows.append(
                    ParentChunk(
                        id=parent_id,
                        doc_id=doc_id,
                        user_id=user_id,
                        section_path=parent.section_path,
                        content=parent.content,
                        char_count=len(parent.content),
                        seq=seq,
                    )
                )
            await self.repo.add_parents(parent_rows)

            milvus_rows = []
            # 造 Milvus 行
            for index, child in enumerate(children):
                parent_id = parent_rows[child.parent_index].id
                # `child.parent_index` 终于派上用场 —— `parent_rows[下标]` 反查父块 ID
                milvus_rows.append(
                    {
                        "child_id": hashlib.sha1(f"{doc_id}{index}".encode("utf-8")).hexdigest()[:32],
                        # 用 `index`（子块序号）而不是内容 hash
                        "doc_id": doc_id,
                        "parent_id": parent_id,
                        "user_id": user_id,
                        "section_path": child.section_path,
                        "content": child.content,
                        "raw_content": child.raw_content,
                        "dense": vectors[index],
                    }
                )
            inserted = insert_children(self.milvus, milvus_rows)

            # 更新状态 + commit
            doc.status = "ready"
            doc.is_indexed = True
            doc.parser = parsed.parser
            doc.page_count = parsed.page_count
            doc.char_count = len(parsed.text)
            doc.token_estimate = int(len(parsed.text) * TOKEN_FACTOR)
            await self.session.commit()
            # `commit` 时才真正发两条 SQL：`INSERT documents` + `INSERT parent_chunks` + `UPDATE documents`

            logger.info(
                "文档入库完成",
                doc_id=doc_id,
                parents=len(parent_rows),
                children=inserted,
                parser=parsed.parser,
            )
            return doc
        #     位置	      算法	长度	    干什么
        # content_hash	sha256	64	  文件指纹，幂等去重
        # parent_id	    sha1	16	  父块确定性 ID，重新解析后仍然不变
        # child_id	    sha1	32	  子块 ID，doc_id + 序号算出来的

        except Exception as exc:
            await self.session.rollback()
            # 解析/向量化失败：不留下半份 PG 数据，但保留一条 failed 记录便于排查。

            # Milvus 可能已经写入（insert_children 在 commit 之前）；
            # PG 回滚后这些子块会变成孤儿，先清掉。
            # 单独兜异常：清理失败不能掩盖原始错误。
            if self.milvus is not None:
                try:
                    delete_by_doc(self.milvus, doc_id, user_id)
                except Exception:
                    logger.exception("清理 Milvus 残留失败", doc_id=doc_id, user_id=user_id)

            failed = Document(
                id=doc_id,
                user_id=user_id,
                filename=filename,
                mime_type=mime_type,
                size_bytes=len(data),
                content_hash=content_hash,
                storage_path=str(target),
                status="failed",
                version=1,
                is_indexed=False,
                error_message=str(exc)[:500],
            )
            await self.repo.add_document(failed)
            await self.session.commit()
            logger.exception("文档入库失败", doc_id=doc_id, filename=filename)
            raise

    async def list_documents(self, user_id: int, limit: int, offset: int) -> Sequence[Document]:
        return await self.repo.list_documents(user_id, limit, offset)

    # 删除：先删 Milvus 再删 PG；Milvus 失败就整单失败，避免留孤儿向量。
    async def delete_document(self, doc_id: str, user_id: int) -> bool:
        doc = await self.repo.get_document(doc_id, user_id)
        if doc is None:
            return False
        if self.milvus is not None:
            delete_by_doc(self.milvus, doc_id, user_id)
        await self.repo.delete_document(doc)
        await self.session.commit()
        return True


    # 用新的切分参数重建一份文档的索引；评测要对比不同 chunk_size 就靠它。
    # 只重建 chunks，不动 documents 那一行（文件本身没变）。
    async def reindex(
        self,
        doc_id: str,
        user_id: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> int:
        if self.milvus is None:
            raise MilvusNotReadyError("Milvus 未就绪")

        doc = await self.repo.get_document(doc_id, user_id)
        if doc is None:
            raise UnsupportedFormatError("文档不存在")

        path = Path(doc.storage_path)
        suffix = path.suffix.lower()
        parsed = parse_document(path, suffix)
        parents = split_parents(parsed.text)
        children = split_children(parents, chunk_size, chunk_overlap)
        if not children:
            raise UnsupportedFormatError("重建后没有可用文本")

        # 先删旧的：Milvus 子块 + PG 父块。删完再写，避免新旧混在一起。
        delete_by_doc(self.milvus, doc_id, user_id)
        await self.repo.delete_parents(doc_id, user_id)

        vectors = embed_texts([child.content for child in children])

        parent_rows: list[ParentChunk] = []
        for seq, parent in enumerate(parents):
            parent_id = hashlib.sha1(
                f"{doc_id}{parent.section_path}{seq}".encode("utf-8")
            ).hexdigest()[:16]
            parent_rows.append(
                ParentChunk(
                    id=parent_id,
                    doc_id=doc_id,
                    user_id=user_id,
                    section_path=parent.section_path,
                    content=parent.content,
                    char_count=len(parent.content),
                    seq=seq,
                )
            )
        await self.repo.add_parents(parent_rows)

        rows = []
        for index, child in enumerate(children):
            rows.append(
                {
                    "child_id": hashlib.sha1(f"{doc_id}{chunk_size}{index}".encode("utf-8")).hexdigest()[:32],
                    "doc_id": doc_id,
                    "parent_id": parent_rows[child.parent_index].id,
                    "user_id": user_id,
                    "section_path": child.section_path,
                    "content": child.content,
                    "raw_content": child.raw_content,
                    "dense": vectors[index],
                }
            )
        inserted = insert_children(self.milvus, rows)

        doc.char_count = len(parsed.text)
        doc.token_estimate = int(len(parsed.text) * TOKEN_FACTOR)
        await self.session.commit()
        logger.info(
            "索引已重建",
            doc_id=doc_id,
            chunk_size=chunk_size,
            parents=len(parent_rows),
            children=inserted,
        )
        return inserted



    # 检索：query 向量化 -> 混合检索 -> 返回父块级结果。
    async def search(
        self,
        user_id: int,
        query: str,
        top_k: int,
        doc_ids: list[str] | None,
    ) -> list[dict]:
        if self.milvus is None:
            raise MilvusNotReadyError("Milvus 未就绪")
        vector = embed_texts([query])[0]
        return hybrid_search(self.milvus, query, vector, user_id, top_k, doc_ids)
