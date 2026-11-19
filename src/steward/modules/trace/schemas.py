from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


# 单步出参；不暴露 user_id（最小暴露）。
class TraceStepOut(BaseModel):
    step: int
    kind: str
    name: str | None
    input: dict | None
    output: dict | None
    latency_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# 一次运行的完整轨迹，steps 已按 step 升序。
class TraceOut(BaseModel):
    run_id: str
    thread_id: str
    steps: list[TraceStepOut]
