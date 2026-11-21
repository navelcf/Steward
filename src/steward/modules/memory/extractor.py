from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel

from steward.core.logging import get_logger

logger = get_logger(__name__)

# 抽取规则常量。绝对不能对它做 .format()：
# 下面 JSON 示例里的 {"should_save" 会被当成占位符，直接 KeyError。
EXTRACT_RULES = """你是记忆抽取器。读下面这轮对话，判断有没有值得【跨会话】记住的内容。大多数情况都无需抽取记忆。

只记四类：任务结论(task_result)、关键决定(decision)、用户明确偏好(preference)、稳定事实(fact)。
不记：寒暄、客套、文档原文摘抄、一次性细节、敏感信息、助手自己的推理过程。

只输出严格 JSON，不要 markdown 代码块，不要任何解释：
{"should_save": true, "kind": "task_result", "title": "不超过30字", "content": "一句话不超过200字", "importance": 4}
没有值得记的就只输出：{"should_save": false}
"""


# 模型偶尔会包一层 ```json，剥掉再解析。
def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        text = text.removesuffix("```").strip()
    return text


# 读一轮对话，抽出一条记忆；不值得记就返回 None。
# 任何异常都返回 None：记忆是锦上添花，不能因为它把主流程弄挂。
async def extract_memory(
    model: BaseChatModel,
    user_text: str,
    answer: str,
) -> dict | None:
    prompt = EXTRACT_RULES + f"\n对话：\n用户：{user_text}\n助手：{answer}\n"
    try:
        message = await model.ainvoke(prompt)
    except Exception:
        logger.exception("记忆抽取调用失败")
        return None

    raw = _strip_fence(str(message.content))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("记忆抽取不是合法 JSON", raw=raw[:200])
        return None

    if not data.get("should_save"):
        return None

    kind = str(data.get("kind") or "")
    title = str(data.get("title") or "").strip()
    content = str(data.get("content") or "").strip()
    try:
        importance = int(data.get("importance") or 3)
    except (TypeError, ValueError):
        importance = 3

    if kind not in {"task_result", "decision", "preference", "fact"} or not title or not content:
        logger.warning("记忆字段不合法，丢弃", kind=kind, title=title[:30])
        return None

    return {
        "kind": kind,
        "title": title[:200],
        "content": content[:2000],
        "importance": max(1, min(5, importance)),
    }
