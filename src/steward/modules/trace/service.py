from __future__ import annotations

import json
import time
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from steward.core.logging import get_logger
from steward.modules.trace.models import RunTrace
from steward.modules.trace.repository import TraceRepository

logger = get_logger(__name__)

# 单字段最大字符数；JSONB 里塞全文会让表迅速膨胀（方案 4.6 第 4 条：大文本不进索引）。
BRIEF_LIMIT = 2000


# 把任意对象压成可 JSON 序列化的短字符串；不可序列化的对象用 str() 兜底。
def brief(value: object, limit: int = BRIEF_LIMIT) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit]
# 把任何东西压成「不超过 2000 字符的字符串」。

# 一次请求一个收集器；只攒内存，流结束（或失败）时批量落库，流式期间零 DB 连接。
class TraceCollector:
    def __init__(
        self,
        run_id: str,
        user_id: int,
        thread_id: str,
        base_step: int = 0,
    ) -> None:
        self.run_id = run_id
        self.user_id = user_id
        self.thread_id = thread_id
        self._rows: list[RunTrace] = []
        self._step = base_step# 已经到第几步了
        self._started: dict[str, float] = {}# 记录开始时间
        self._tool_args: dict[str, tuple[str, object]] = {}# 暂存工具参数

    @property
    def count(self) -> int:
        return len(self._rows)

    # 记开始时间；key 用事件的 run_id，能区分同名的多次调用。
    def begin(self, key: str) -> None:
        self._started[key] = time.perf_counter()
        # 高精度秒表。比 `time.time()` 准，不受系统时间调整影响。专门用来量耗时的。

    # 算耗时并清掉开始时间；没有对应 begin 就返回 None。
    def end(self, key: str) -> int | None:
        start = self._started.pop(key, None)
        # 拿出来的同时删掉。一支表只用一次，留着浪费
        if start is None:
            return None
        return int((time.perf_counter() - start) * 1000)
        # `perf_counter` 返回的是秒，列叫 `latency_ms`，要毫秒

    # 工具开始时只暂存参数，等结束才拼一条完整记录（否则 input/output 分两条）。
    def remember_tool(self, key: str, name: str, args: object) -> None:
        self._tool_args[key] = (name, args)

    def pop_tool(self, key: str) -> tuple[str, object] | None:
        return self._tool_args.pop(key, None)
    # LangGraph 给你两条事件：
    # - `on_tool_start` → 你知道「要调 `save_note`，参数是 X」，但不知道结果
    # - `on_tool_end` → 你才知道「返回了 `4/xxx.md`」

    # 追加一行；step 自增，保证同一 run_id 内严格有序。
    def add(
        self,
        kind: str,
        name: str | None = None,
        input_data: object = None,
        output_data: object = None,
        latency_ms: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        self._step += 1
        self._rows.append(
            RunTrace(
                run_id=self.run_id,
                user_id=self.user_id,
                thread_id=self.thread_id,
                step=self._step,
                kind=kind,
                name=name,
                input={"brief": brief(input_data)} if input_data is not None else None,
                # `input` 列是 `JSONB`（存 JSON 对象）。
                # 外层套一层，统一成「对象里有个 brief 字段」，查询时 `input->>'brief'` 就好取
                # 因为有些步骤没有输入（比如 `approval` 步骤可能只有输出）
                output={"brief": brief(output_data)} if output_data is not None else None,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )

    # 批量落库；空列表直接返回。失败只记日志，绝不让 trace 拖垮主流程。
    async def flush(self, factory: async_sessionmaker[AsyncSession]) -> None:
        if not self._rows:
            return
        rows: Sequence[RunTrace] = list(self._rows)
        self._rows.clear()
        try:
            async with factory() as session:
                await TraceRepository(session).add_all(rows)
                await session.commit()
        except Exception:
            logger.exception("轨迹落库失败", run_id=self.run_id, steps=len(rows))