from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from steward.common.models import Base, CreatedAtMixin


# 一次评测运行：一行一个 label，指标是这次跑出来的平均值（方案 4.3）。
# 一行 = 一次跑批（12 题的整体成绩）
class EvalRun(Base, CreatedAtMixin):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # 人可读的标签，例如 chunk400_ov60_top20；对比时按它查。
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    # 这次用的参数快照（chunk_size / overlap / top_k / min_score / final_k）。
    # {"chunk_size": 400, "chunk_overlap": 60, "top_k": 20, "final_k": 6}
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # 今天能算出来的三个（规则）；没有就存 NULL，不填 0 冒充。
    context_recall: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    context_precision: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    refusal_rate: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)

    # 要裁判模型的三个，今天恒为 NULL（方案 10.3 的口径先占住，别改名）。
    faithfulness: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    answer_relevancy: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    tool_correctness: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)

    # 题量与耗时；和上次比耗时涨了也值得看一眼。
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 钱没接计费，先留着列。
    total_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # 拿哪一次当基线；对比时用它。
    baseline_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (Index("idx_eval_runs_label", "label", "created_at"),)


# 单题明细：一次 run 有多行；出报告时要按题看哪条挂了（方案 4.3）。
# 一行 = 一次跑批里的一道题（12 行/批）
class EvalCaseResult(Base):
    __tablename__ = "eval_case_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[str] = mapped_column(String(32), nullable=False)
    # 今天不跑生成，answer 恒 NULL。
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 这题召回的片段（就是 retrieve_sources 的返回值）。
    sources: Mapped[list[dict] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    # 这题的各项指标 + 命中详情，JSONB 灵活放。
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_case_results_run", "run_id"),)