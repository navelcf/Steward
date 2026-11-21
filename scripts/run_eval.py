from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from steward.core.config import settings
from steward.core.logging import configure_logging
from steward.infra.milvus import get_milvus_client
from steward.modules.eval.models import EvalCaseResult, EvalRun
from steward.modules.eval.repository import EvalRepository
from steward.modules.eval.service import aggregate, compare_runs, evaluate_case
from steward.modules.knowledge.retriever import retrieve_sources
from steward.modules.knowledge.service import KnowledgeService
import steward.modules.auth.models  # noqa: F401  ← 注册 users 表；否则 reindex 提交时外键解析会崩

CASES_PATH = Path(__file__).resolve().parents[1] / "tests" / "eval_cases" / "rag_v1.jsonl"
DEFAULT_USER_ID = 4


def load_cases() -> list[dict]:
    lines = [line for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


async def run(args: argparse.Namespace) -> None:
    engine = create_async_engine(settings.db.url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    milvus = get_milvus_client()

    # 1. 可选：先用新参数重建索引。
    if args.chunk_size:
        async with factory() as session:
            docs = await KnowledgeService(session, milvus).list_documents(args.user_id, 50, 0)
            for doc in docs:
                if doc.status != "ready":
                    continue
                await KnowledgeService(session, milvus).reindex(
                    doc.id, args.user_id, args.chunk_size, args.chunk_overlap
                )
        print(f"[rebuild] chunk_size={args.chunk_size} overlap={args.chunk_overlap}")

    # 2. 逐题检索。
    cases = load_cases()
    rows: list[dict] = []
    async with factory() as session:
        for case in cases:
            started = time.perf_counter()
            sources = await retrieve_sources(
                session,
                milvus,
                args.user_id,
                case["question"],
                top_k=args.top_k,
                final_k=args.final_k,
            )
            latency = int((time.perf_counter() - started) * 1000)
            metrics = evaluate_case(case, sources)
            rows.append(
                {
                    "case": case,
                    "is_answerable": case.get("is_answerable", True),
                    "metrics": metrics,
                    "latency_ms": latency,
                    "sources": sources,
                }
            )
            flag = "OK " if metrics["recall"] >= 0.5 else "MISS"
            print(f"  [{flag}] {case['id']} {case['question'][:26]} -> hits={metrics['hit_count']} {latency}ms")

        # 3. 聚合 + 落库。
        summary = aggregate(rows)
        run_id = str(uuid4())
        config = {
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "top_k": args.top_k,
            "final_k": args.final_k,
        }
        repo = EvalRepository(session)

        baseline = await repo.latest_by_label(args.baseline) if args.baseline else None
        await repo.add_run(
            EvalRun(
                id=run_id,
                user_id=args.user_id,
                label=args.label,
                config_json=config,
                context_recall=summary["context_recall"],
                context_precision=summary["context_precision"],
                refusal_rate=summary["refusal_rate"],
                case_count=summary["case_count"],
                avg_latency_ms=summary["avg_latency_ms"],
                baseline_run_id=baseline.id if baseline else None,
            )
        )
        await repo.add_results(
            [
                EvalCaseResult(
                    run_id=run_id,
                    case_id=row["case"]["id"],
                    sources=row["sources"] or None,
                    metrics=row["metrics"],
                    passed=row["metrics"]["recall"] >= 0.5,
                    fail_reason=None if row["metrics"]["recall"] >= 0.5 else "未命中期望章节",
                )
                for row in rows
            ]
        )
        await session.commit()

    print(f"\n=== run {args.label} ({run_id[:8]}) ===")
    for key in ("context_recall", "context_precision", "refusal_rate", "case_count", "avg_latency_ms"):
        print(f"  {key:18s} = {summary[key]}")

    # 4. 有基线就对比，并决定退出码。
    if baseline is not None:
        passed, diffs = compare_runs(
            {
                "context_recall": baseline.context_recall,
                "context_precision": baseline.context_precision,
                "refusal_rate": baseline.refusal_rate,
            },
            summary,
        )
        print(f"\n=== 对比基线 {baseline.label} ({baseline.id[:8]}) ===")
        for diff in diffs:
            mark = "—" if diff["ok"] is None else ("OK" if diff["ok"] else "FAIL")
            print(
                f"  [{mark:4s}] {diff['metric']:18s} {diff['baseline']} -> {diff['current']} "
                f"(Δ {diff['delta']})"
            )
        if not passed:
            raise SystemExit(1)

    await engine.dispose()
    milvus.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Steward 检索质量评测")
    parser.add_argument("--label", required=True, help="本次运行的标签，例如 chunk400_top20")
    parser.add_argument("--baseline", default="", help="基线 run 的 label；给了就做门禁对比")
    parser.add_argument("--chunk-size", type=int, default=0, help="给了就先按这个参数重建索引")
    parser.add_argument("--chunk-overlap", type=int, default=60)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=6)
    parser.add_argument("--user-id", type=int, default=DEFAULT_USER_ID)
    args = parser.parse_args()

    configure_logging("WARNING")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()