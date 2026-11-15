# 上传的全部业务逻辑：校验、生成安全文件名、分块落盘、抽文本、算字数。

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from steward.core.config import APP_ROOT
from steward.core.logging import get_logger
from steward.modules.file.schemas import FileOut  # 出参规范

logger = get_logger(__name__)
# 上传和前面操作数据库可不一样！失败原因有很多！需要日志抛出来！

STORAGE_ROOT = (APP_ROOT / "storage").resolve()  # 保存路径
MAX_FILE_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
ALLOWED_SUFFIXES = {".docx", ".pdf", ".md", ".txt"}
TOKEN_FACTOR = 0.75


# 业务异常；router 负责把它们翻成 HTTP 状态码，service 自己不认识 HTTP。
class UnsupportedFileError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


# `docx` 和 `pypdf` 是重库。`pypdf` 一导入要几十毫秒。需要的时候才导入！
# 按校验过的后缀选解析器；绝不用客户端传的 content_type 判断。
def extract_text(path: Path, suffix: str) -> str:
    if suffix == ".docx":
        from docx import Document

        return "\n".join(p.text for p in Document(str(path)).paragraphs)
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
        # 加密页或者图片页返回none
    return path.read_text(encoding="utf-8", errors="ignore")


# 上传主流程：校验后缀 -> 生成安全文件名 -> 分块落盘 -> 抽文本 -> 返回元数据。
async def save_upload(file: UploadFile, user_id: int) -> FileOut:
    original_name = file.filename or ""
    suffix = Path(original_name).suffix.lower()
    # `pathlib.Path` 是 "路径字符串的解析工具"。你给它一个文件名，它能切出各个部分
    if suffix not in ALLOWED_SUFFIXES:
        raise UnsupportedFileError(f"不支持的文件类型：{suffix or '未知'}")

    file_id = str(uuid4())
    user_dir = (STORAGE_ROOT / str(user_id)).resolve()
    if not user_dir.is_relative_to(STORAGE_ROOT):
        # Path("E:/Steward/storage/../../etc/passwd").is_relative_to("E:/Steward/storage")  →  False
        # 这也太全面了，这谁能想到？E:/etc/passwd
        raise RuntimeError("非法的存储路径")
    user_dir.mkdir(parents=True, exist_ok=True)
    # `parents=True`：`storage` 和 `storage/4` 都不存在时，两层一起建
    # `exist_ok=True`：已经存在了不报错。

    target = (user_dir / f"{file_id}{suffix}").resolve()
    if not target.is_relative_to(STORAGE_ROOT):
        raise RuntimeError("非法的存储路径")
    # 双重校验

    size = 0
    created = False
    try:
        # "xb" 是独占创建：万一 uuid 撞了已存在的文件，直接失败而不是覆盖别人的数据。
        # 这真是魔了，前面user_id不撞？感觉是无效校验。
        with target.open("xb") as out:
            created = True
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                # `:=` 叫海象运算符。它的作用是 "赋值并返回赋值结果"。
                # 每块先累加 `size`、超限立刻抛，再 `write`。所以超限那一块不会被写进去。
                if size > MAX_FILE_SIZE:
                    raise FileTooLargeError("文件超过 50MB")
                out.write(chunk)  #  最后才写
        text = extract_text(target, suffix)  # 抽文本
    except FileTooLargeError:
        if created:
            target.unlink(missing_ok=True)
            # 删掉！
            # `missing_ok=True` 意思是 "文件不存在也不报错"
        raise
    except Exception as exc:
        # 解析失败等其它异常：只删本次刚创建的半成品，别动已存在的文件。
        if created:  # 真撞上了这里也不会执行，不会删别人的数据。
            target.unlink(missing_ok=True)
        raise RuntimeError("文件解析失败") from exc
    finally:
        await file.close()

    char_count = len(text)
    token_estimate = int(char_count * TOKEN_FACTOR)  # int向下取整，尽可能少报
    logger.info(
        "文件上传完成",
        user_id=user_id,
        file_id=file_id,
        suffix=suffix,
        size=size,
        char_count=char_count,
    )
    return FileOut(
        file_id=file_id,
        filename=original_name,
        suffix=suffix,
        size=size,
        char_count=char_count,
        token_estimate=token_estimate,
    )
