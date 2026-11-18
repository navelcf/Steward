from __future__ import annotations

from datetime import datetime

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from steward.modules.file.service import STORAGE_ROOT

from uuid import UUID, uuid4


# 工具入参用 pydantic（方案 9.3 L1063）；Field(description=...) 会进 JSON Schema 给模型看。
class SaveNoteArgs(BaseModel):
    content: str = Field(min_length=1, max_length=4000, description="要保存的笔记正文")


# 笔记根目录放在 storage/ 下，复用 Day 5 已忽略的目录，不用改 .gitignore。
# resolve() 保证后面 is_relative_to 的两层比较都在绝对路径上做。
NOTES_ROOT = (STORAGE_ROOT / "notes").resolve()

# 描述只写一处：@tool 和注册表都引用同一个常量，避免改了一处忘了另一处。
# 拆成两段拼接而不是一整行，也是为了不超 ruff 的 120 字符行宽。
GET_TIME_DESC = "返回当前服务器本地时间（ISO 8601 带时区）。当用户问“现在几点”“今天几号”时调用，不要自己编时间。"
SAVE_NOTE_DESC = (
    "把一段文字保存成 markdown 笔记文件（.md），返回保存后的相对路径。仅在用户明确说“记下来”“保存笔记”时调用。"
)


# 只读工具：默认 auto，今天就能被模型调用。
@tool(description=GET_TIME_DESC)  # args_schema在被tool修饰的时候就已经创建好了
def get_current_time() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
    # astimezone()               → 补上本地时区，变成 aware
    # isoformat(timespec="seconds")  → "2026-11-16T15:30:00+08:00"


# 有副作用的工具：默认 ask。user_id 由闭包注入，模型看不到也传不了（防越权）。
# 唉哟我去，又学习到了，这确实有水平的！
# note_id 由审批单 id 注入：同一次审批只落一个文件，重入不会写第二份。
def build_save_note(user_id: int, note_id: str | None = None) -> BaseTool:
    @tool(description=SAVE_NOTE_DESC, args_schema=SaveNoteArgs)
    def save_note(content: str) -> str:
        target_dir = (NOTES_ROOT / str(user_id)).resolve()
        # 两层路径校验：目录和最终文件都必须在 NOTES_ROOT 下。
        if not target_dir.is_relative_to(NOTES_ROOT):
            raise ValueError("笔记目录非法")
        target_dir.mkdir(parents=True, exist_ok=True)

        # note_id 来自审批单（uuid4 字符串），先校验格式再当文件名用。
        name = note_id or str(uuid4())
        try:
            UUID(name)
        except ValueError as exc:
            raise ValueError("笔记标识非法") from exc

        target = (target_dir / f"{name}.md").resolve()
        if not target.is_relative_to(NOTES_ROOT):
            raise ValueError("笔记路径非法")
        if target.exists():  # 文件已存在
            return target.relative_to(NOTES_ROOT).as_posix()  # 把所有反斜杠换成正斜杠。
        target.write_text(content, encoding="utf-8")
        return target.relative_to(NOTES_ROOT).as_posix()  # 把所有反斜杠换成正斜杠。
        # relative_to()  → 相对路径,不暴露目录结构

    return save_note


# 注册表元信息与可执行对象的对应关系；key 必须和 ToolRegistry.name 一致。
BUILTIN_META: dict[str, dict[str, str]] = {
    "get_current_time": {
        "display_name": "当前时间",
        "description": GET_TIME_DESC,
        "policy": "auto",
        "risk_note": "",
    },
    "save_note": {
        "display_name": "保存笔记",
        "description": SAVE_NOTE_DESC,
        "policy": "ask",
        "risk_note": "将写入本地笔记文件",
    },
}
