from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from steward.common.models import Base, CreatedAtMixin, UpdatedAtMixin


# 知识库文档；一行一个上传物，content_hash 用于增量判断（方案 4.3）。
class Document(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    # 原始文件名
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # 文件类型，pdf/word/md...
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 文件大小字节
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # sha256 十六进制 64 位；同一用户同一内容同一版本只存一次。
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    # 存储路径
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    # 文件状态：`uploaded` → `parsing` → `indexed` / `failed`
    # 为什么要状态机： 因为「解析 PDF」是耗时操作（一份 100 页 PDF 可能要 10 秒）。
    # 不能同步等，必须「先落库标记 uploaded，后台异步解析，成功改 indexed」。
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 默认版本号为1
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 解析后的统计（可空），因为上传时还不知道
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 失败原因`status='failed'` 时才有值
    is_indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 向量是否已进 Milvus`false` / `true`
    parser: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 解析器名字，便于将来对比 pypdf / mineru 的效果。

    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", "version", name="uq_documents_user_hash_version"),
        # 数据库层面不让「这三列的组合」出现两次
        # 场景：用户手滑，同一个 `合同法.pdf` 传了两次。
        Index("idx_documents_user_status", "user_id", "status"),
    )


# 父块（完整章节）；子块在 Milvus，通过 parent_id 关联回来。
class ParentChunk(Base, CreatedAtMixin):
    __tablename__ = "parent_chunks"

    # 切分阶段生成：sha1(doc_id + section_path + seq)[:16]，不依赖自增。
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # FK → documents级联删
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    section_path: Mapped[str] = mapped_column(String(500), nullable=False)
    # `"第3章 > 3.2 责任免除"`章节路径
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 父块全文`Text`，无上限
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # 字数用于「是否超 4096」的判断
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    # 在文档里的顺序`0, 1, 2...`

    __table_args__ = (Index("idx_parent_doc_seq", "doc_id", "seq"),)
