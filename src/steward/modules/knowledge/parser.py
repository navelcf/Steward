# 拆成三块：解析、父块、子块
# 一个文件（.pdf / .docx / .md / .txt）
#         ↓  第 1 件事：读
#      纯文本（一大段 str）
#         ↓  第 2 件事：切
#   父块 list[ParentBlock]  →  子块 list[ChildBlock]

from __future__ import annotations

import re  # `re` = 正则表达式
from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from functools import lru_cache


# 父块上限：超过就按段落再切，section_path 加 (续N)（方案 7.3 L870）。
MAX_PARENT_CHARS = 3000
# 子块参数照方案 7.3 L876。
CHILD_SIZE = 400
CHILD_OVERLAP = 60
# 切太粗 → 向量糊；切太细 → 上下文碎。
# 400 / 60 / 3000 这三个数就是这条链路的「旋钮」，先按教程的默认值跑，等有了真实数据再调。


# Markdown 标题：MinerU 返回的就是这种，pypdf 抽出来的通常没有。
HEADING = re.compile(r"^(#{1,6})\s+(.+)$")


# `frozen=True` = 不可变
@dataclass(frozen=True)
class ParsedDoc:  # 读的产物：一篇纯文本
    text: str
    page_count: int | None
    parser: str


@dataclass(frozen=True)  # 切父块的产物：一节正文
class ParentBlock:
    section_path: str
    content: str


@dataclass(frozen=True)  # 切子块的产物
class ChildBlock:
    parent_index: int  # 是整数下标，不是父块 ID
    section_path: str
    content: str
    raw_content: str


# 解析入口：按后缀分派。MinerU 接入时只改这里，上层不动。
def parse_document(path: Path, suffix: str) -> ParsedDoc:
    suffix = suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix == ".docx":
        return _parse_docx(path)
    return _parse_plain(path)


# `_` 开头是「模块内部函数」的约定—— 表示「别从别的模块 import 它」
# PDF 抽不出标题，`section_path` 全叫「正文」
# 所以以后需要mineru
def _parse_pdf(path: Path) -> ParsedDoc:
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return ParsedDoc(text="\n\n".join(pages), page_count=len(pages), parser="pypdf")


# 逐页抽文字，页与页之间用空行 `\n\n` 拼起来
# `.strip()`：去掉每页首尾空白


def _parse_docx(path: Path) -> ParsedDoc:
    # docx 的标题样式能直接转成 Markdown 标题，比 PDF 干净。
    doc = DocxDocument(str(path))
    lines: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if style.startswith("heading"):  # 判断「这是不是标题段落」
            digits = "".join(ch for ch in style if ch.isdigit()) or "1"
            lines.append(f"{'#' * min(int(digits), 6)} {text}")  # `"Heading 2"` → `"##"`
            # Markdown 最多 6 级标题，Word 可能有「标题 9」，硬砍到 6。
            # 这也是后面 `HEADING` 正则只认 `#{1,6}` 的原因 —— 两边对齐。
        else:
            lines.append(text)
    return ParsedDoc(text="\n\n".join(lines), page_count=None, parser="python-docx")


def _parse_plain(path: Path) -> ParsedDoc:
    return ParsedDoc(
        text=path.read_text(encoding="utf-8", errors="ignore"),
        # errors="ignore"，遇到非法字节就跳过，不报错。
        # 因为用户传的文件编码不可控，宁可丢几个乱码字符，也别让整个解析失败。
        page_count=None,
        parser="plain",
    )


# 父块：按 Markdown 标题切；没有标题就整体当一块，再按长度切。
def split_parents(text: str) -> list[ParentBlock]:
    blocks: list[tuple[str, str]] = []  # 已完成的 (标题路径, 正文)
    stack: list[str] = []  # 标题栈
    title = "正文"  # 当前标题
    buf: list[str] = []  # 当前块的行缓冲

    def flush(current_title: str, lines: list[str]) -> None:
        body = "\n".join(lines).strip()
        if body:
            blocks.append((current_title, body))

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = HEADING.match(line.strip())
        if match:
            flush(title, buf)
            buf = []
            level = len(match.group(1))
            # 用级别维护标题栈，拼出「第3章 > 3.2 责任免除」。
            stack = stack[: level - 1] + [match.group(2).strip()]
            title = " > ".join(stack) or "正文"
            continue
        buf.append(line)
    flush(title, buf)

    # 超长父块按空行再切，section_path 加 (续N)。
    parents: list[ParentBlock] = []
    for section_path, body in blocks:
        if len(body) <= MAX_PARENT_CHARS:
            parents.append(ParentBlock(section_path=section_path, content=body))
            continue
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        current: list[str] = []
        current_len = 0
        part = 0
        for para in paragraphs:
            if current and current_len + len(para) > MAX_PARENT_CHARS:
                suffix = f" (续{part})" if part else ""
                parents.append(ParentBlock(section_path=f"{section_path}{suffix}", content="\n\n".join(current)))
                part += 1
                current = []
                current_len = 0
            current.append(para)
            current_len += len(para)
        if current:
            suffix = f" (续{part})" if part else ""
            parents.append(ParentBlock(section_path=f"{section_path}{suffix}", content="\n\n".join(current)))

    return parents


# 子块：在父块内部递归切；content 带 section_path，raw_content 只留正文。
@lru_cache(maxsize=8)  # 按参数缓存，评测时反复换参数不会反复建对象。
def _splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    # 经典切分器；按参数缓存，评测时反复换参数不会反复建对象。
    # 1. 先试着用 `\n\n`（段落）切
    # 2. 切出来某块还超 → 改用 `\n`（换行）切
    # 3. 还超 → 改用 `。`（句号）
    # 4. 还超 → `；`（分号）
    # 5. 还超 → ` `（空格硬切）
    # 不设 keep_separator 的话，句子结尾的标点会消失。
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", " "],
        keep_separator="end",
    )


def split_children(
    parents: list[ParentBlock],
    chunk_size: int = CHILD_SIZE,
    chunk_overlap: int = CHILD_OVERLAP,
) -> list[ChildBlock]:
    children: list[ChildBlock] = []
    splitter = _splitter(chunk_size, chunk_overlap)
    for index, parent in enumerate(parents):
        for piece in splitter.split_text(parent.content):
            piece = piece.strip()
            if not piece:
                continue
            children.append(
                ChildBlock(
                    parent_index=index,
                    section_path=parent.section_path,
                    content=f"{parent.section_path}\n{piece}",
                    # 带标题，进Milvus 的 `content` 字段（进向量、进 BM25）
                    raw_content=piece,  # 不带标题
                    # 只作副本，喂模型用的是 parent_chunks.content（父块全文），不是这个
                )
            )
    return children
