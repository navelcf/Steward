# 指标计算
from __future__ import annotations

from typing import Any

# 门禁阈值：任一指标比基线跌超过 3 个百分点就判失败（方案 10.3）。
MAX_DROP = 0.03

# 参与门禁的指标；没算出来的（None）跳过，不当成 0。
GATED_METRICS = ("context_recall", "context_precision", "refusal_rate")


# 单题打分：只看检索结果，不调模型。
def evaluate_case(case: dict, sources: list[dict]) -> dict:
    sections = case.get("expected_sections") or []
    keywords = case.get("expected_keywords") or []

    # 每个命中片段是否「有用」：章节对得上，或内容里出现关键词。
    hits: list[bool] = []
    for src in sources:
        by_section = any(exp in (src.get("section_path") or "") for exp in sections)
        by_keyword = any(kw in (src.get("content") or "") for kw in keywords)
        hits.append(by_section or by_keyword)

    # 无答案题：正确行为是「一条都不返回」，即拒答。
    if not case.get("is_answerable", True):
        refused = len(sources) == 0
        return {
            "recall": 1.0 if refused else 0.0,
            "precision": 1.0 if refused else 0.0,
            "refused": refused,
            "hit_count": 0,
            "top_hit": None,
        }

    # 有答案题：只要有一条命中就算召回；一条都没命中就是 0。
    recall = 1.0 if any(hits) else 0.0

    # precision 看「有用片段排得靠不靠前」：每个命中位置的准确率取平均。
    precisions = [
        sum(hits[: i + 1]) / (i + 1)
        for i, flag in enumerate(hits)
        if flag
    ]
    precision = sum(precisions) / len(precisions) if precisions else 0.0

    return {
        "recall": recall,
        "precision": precision,
        "refused": len(sources) == 0,
        "hit_count": sum(hits),
        "top_hit": next((src.get("section_path") for src, flag in zip(sources, hits) if flag), None),
    }


# 聚合：有答案题和无答案题分开算，别混在一起。
def aggregate(rows: list[dict]) -> dict[str, Any]:
    answerable = [r for r in rows if r["is_answerable"]]
    unanswerable = [r for r in rows if not r["is_answerable"]]

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    return {
        "context_recall": mean([r["metrics"]["recall"] for r in answerable]),
        "context_precision": mean([r["metrics"]["precision"] for r in answerable]),
        # 拒答率的分母是「无答案题」，不是全部题。
        "refusal_rate": mean([1.0 if r["metrics"]["refused"] else 0.0 for r in unanswerable]),
        "case_count": len(rows),
        "avg_latency_ms": int(sum(r["latency_ms"] for r in rows) / len(rows)) if rows else None,
    }


# 对比两次 run：返回（是否通过，逐项差异）。
def compare_runs(baseline: dict, current: dict) -> tuple[bool, list[dict]]:
    diffs: list[dict] = []
    passed = True
    for name in GATED_METRICS:
        old = baseline.get(name)
        new = current.get(name)
        if old is None or new is None:
            diffs.append({"metric": name, "baseline": old, "current": new, "delta": None, "ok": None})
            continue
        delta = round(float(new) - float(old), 4)
        ok = delta >= -MAX_DROP
        passed = passed and ok
        diffs.append({"metric": name, "baseline": old, "current": new, "delta": delta, "ok": ok})
    return passed, diffs