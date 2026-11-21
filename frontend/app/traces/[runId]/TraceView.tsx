"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
    AlertTriangle,
    ArrowLeft,
    Check,
    Copy,
    GitBranch,
    Loader2,
    MessageSquare,
    RefreshCw,
} from "lucide-react";
import BrandMark from "@/components/BrandMark";
import ThemeToggle from "@/components/ThemeToggle";
import TraceTimeline from "@/components/TraceTimeline";
import { getTrace } from "@/lib/api";
import { formatDateTime, formatDuration, formatNumber } from "@/lib/format";
import type { Trace } from "@/lib/types";

export default function TraceView({ runId }: { runId: string }) {
    const [trace, setTrace] = useState<Trace | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [copied, setCopied] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        let cancelled = false;

        (async () => {
            setLoading(true);
            setError("");
            try {
                const data = await getTrace(runId);
                if (!cancelled) setTrace(data);
            } catch (err) {
                if (!cancelled) setError(err instanceof Error ? err.message : "轨迹加载失败");
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [runId, reloadKey]);

    const totals = useMemo(() => {
        if (!trace) return { latency: 0, prompt: 0, completion: 0, models: 0, tools: 0, approvals: 0 };
        return trace.steps.reduce(
            (acc, step) => ({
                latency: acc.latency + (step.latency_ms ?? 0),
                prompt: acc.prompt + (step.prompt_tokens ?? 0),
                completion: acc.completion + (step.completion_tokens ?? 0),
                models: acc.models + (step.kind === "model" ? 1 : 0),
                tools: acc.tools + (step.kind === "tool" ? 1 : 0),
                approvals: acc.approvals + (step.kind === "approval" ? 1 : 0),
            }),
            { latency: 0, prompt: 0, completion: 0, models: 0, tools: 0, approvals: 0 }
        );
    }, [trace]);

    async function copyRunId() {
        try {
            await navigator.clipboard.writeText(runId);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1600);
        } catch {
            // 忽略
        }
    }

    return (
        <main className="min-h-[100dvh] bg-background">
            <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur-md">
                <div className="mx-auto flex h-14 max-w-4xl items-center gap-3 px-4">
                    <Link
                        href={trace ? `/?thread=${trace.thread_id}` : "/"}
                        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                    >
                        <ArrowLeft className="size-3.5" />
                        回到对话
                    </Link>
                    <span className="h-4 w-px bg-border" />
                    <BrandMark className="size-7" />
                    <div className="min-w-0 flex-1">
                        <h1 className="truncate text-sm font-semibold tracking-tight">运行轨迹</h1>
                        <p className="truncate text-[10px] text-muted-foreground">
                            模型调用 · 工具参数 · 审批 · 耗时与 token
                        </p>
                    </div>
                    <ThemeToggle />
                </div>
            </header>

            <div className="mx-auto max-w-4xl px-4 py-6">
                {loading && (
                    <div className="space-y-3">
                        <div className="skeleton h-24 rounded-2xl" />
                        {[0, 1, 2, 3].map((index) => (
                            <div key={index} className="skeleton h-16 rounded-xl" />
                        ))}
                    </div>
                )}

                {!loading && error && (
                    <div className="rounded-2xl border border-destructive/25 bg-destructive/5 px-6 py-10 text-center">
                        <AlertTriangle className="mx-auto size-6 text-destructive" />
                        <p className="mt-3 text-sm font-medium text-destructive">{error}</p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                            run_id 不存在，或者这次运行不属于当前账号。
                        </p>
                        <button
                            type="button"
                            onClick={() => setReloadKey((value) => value + 1)}
                            className="mt-4 inline-flex items-center gap-1.5 rounded-lg border bg-card px-3 py-1.5 text-xs transition-colors hover:bg-accent"
                        >
                            <RefreshCw className="size-3.5" />
                            重试
                        </button>
                    </div>
                )}

                {!loading && !error && trace && (
                    <div className="space-y-4">
                        <section className="rounded-2xl border bg-card p-4">
                            <div className="flex flex-wrap items-center gap-2">
                                <GitBranch className="size-4 text-muted-foreground" />
                                <span className="text-sm font-medium tracking-tight">这次运行</span>
                                <span className="rounded-full border bg-muted/50 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                                    {trace.run_id.slice(0, 8)}…{trace.run_id.slice(-4)}
                                </span>
                                <button
                                    type="button"
                                    onClick={copyRunId}
                                    className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                    title="复制完整 run_id"
                                >
                                    {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
                                </button>

                                <Link
                                    href={`/?thread=${trace.thread_id}`}
                                    className="ml-auto inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                >
                                    <MessageSquare className="size-3" />
                                    打开所属会话
                                </Link>
                            </div>

                            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                                {[
                                    { label: "步数", value: formatNumber(trace.steps.length) },
                                    { label: "总耗时", value: formatDuration(totals.latency) },
                                    { label: "输入 tokens", value: formatNumber(totals.prompt) },
                                    { label: "输出 tokens", value: formatNumber(totals.completion) },
                                ].map((item) => (
                                    <div key={item.label} className="rounded-xl bg-muted/50 px-3 py-2">
                                        <p className="text-[10px] text-muted-foreground">{item.label}</p>
                                        <p className="mt-0.5 text-sm font-semibold tabular-nums">{item.value}</p>
                                    </div>
                                ))}
                            </div>

                            <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
                                <span className="rounded bg-muted px-1.5 py-0.5">模型 {totals.models}</span>
                                <span className="rounded bg-muted px-1.5 py-0.5">工具 {totals.tools}</span>
                                <span className="rounded bg-muted px-1.5 py-0.5">审批 {totals.approvals}</span>
                                <span className="ml-auto">
                                    开始于 {trace.steps[0] ? formatDateTime(trace.steps[0].created_at) : "—"}
                                </span>
                            </div>
                        </section>

                        <section className="rounded-2xl border bg-card p-4">
                            <h2 className="mb-4 text-xs font-medium text-muted-foreground">时间线</h2>
                            {trace.steps.length === 0 ? (
                                <p className="py-8 text-center text-xs text-muted-foreground">这次运行没有留下步骤。</p>
                            ) : (
                                <TraceTimeline steps={trace.steps} />
                            )}
                        </section>

                        <p className="px-1 text-[10px] leading-relaxed text-muted-foreground">
                            轨迹是后端 <code className="rounded bg-muted px-1">run_traces</code> 表的直接投影：
                            每次模型/工具/审批都会落一行，按 step 升序排。参数与输出可能包含敏感内容，只会展示给当前账号。
                        </p>
                    </div>
                )}

                {!loading && !error && !trace && (
                    <div className="rounded-2xl border border-dashed px-6 py-14 text-center">
                        <Loader2 className="mx-auto size-5 animate-spin text-muted-foreground" />
                        <p className="mt-3 text-xs text-muted-foreground">正在读取轨迹…</p>
                    </div>
                )}
            </div>
        </main>
    );
}
