"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowUpRight,
    Check,
    Copy,
    FileText,
    GitBranch,
    Maximize2,
    Minimize2,
    X,
} from "lucide-react";
import TraceTimeline from "./TraceTimeline";
import type { Source, Trace } from "@/lib/types";
import { getTrace } from "@/lib/api";
import { formatDuration, formatNumber } from "@/lib/format";
import { cn } from "@/lib/cn";

type Tab = "sources" | "trace";

type Props = {
    open: boolean;
    onClose: () => void;
    tab: Tab;
    onTabChange: (tab: Tab) => void;
    sources: Source[];
    activeSourceId: string | null;
    onSelectSource: (sourceId: string) => void;
    runId: string | null;
};

export default function Inspector({
    open,
    onClose,
    tab,
    onTabChange,
    sources,
    activeSourceId,
    onSelectSource,
    runId,
}: Props) {
    const router = useRouter();
    const [expanded, setExpanded] = useState<string | null>(null);
    const [trace, setTrace] = useState<Trace | null>(null);
    const [traceLoading, setTraceLoading] = useState(false);
    const [traceError, setTraceError] = useState("");
    const [copied, setCopied] = useState(false);

    // 点正文里的引用芯片时，等右栏渲染出来再滚到对应卡片。
    useEffect(() => {
        if (!activeSourceId) return;
        const timer = window.setTimeout(() => {
            document.getElementById(`source-${activeSourceId}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }, 80);
        return () => window.clearTimeout(timer);
    }, [activeSourceId]);

    useEffect(() => {
        if (tab !== "trace" || !runId) return;
        let cancelled = false;

        (async () => {
            setTraceLoading(true);
            setTraceError("");
            try {
                const data = await getTrace(runId);
                if (!cancelled) setTrace(data);
            } catch (error) {
                if (!cancelled) setTraceError(error instanceof Error ? error.message : "轨迹加载失败");
            } finally {
                if (!cancelled) setTraceLoading(false);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [tab, runId]);

    const totals = useMemo(() => {
        if (!trace) return { latency: 0, prompt: 0, completion: 0 };
        return trace.steps.reduce(
            (acc, step) => ({
                latency: acc.latency + (step.latency_ms ?? 0),
                prompt: acc.prompt + (step.prompt_tokens ?? 0),
                completion: acc.completion + (step.completion_tokens ?? 0),
            }),
            { latency: 0, prompt: 0, completion: 0 }
        );
    }, [trace]);

    async function copyRunId() {
        if (!runId) return;
        try {
            await navigator.clipboard.writeText(runId);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1600);
        } catch {
            // 忽略
        }
    }

    return (
        <>
            {open && (
                <div
                    className="fixed inset-0 z-30 bg-foreground/25 backdrop-blur-[2px] xl:hidden"
                    onClick={onClose}
                    aria-hidden
                />
            )}

            <aside
                className={cn(
                    "fixed inset-y-0 right-0 z-40 flex w-[340px] shrink-0 flex-col border-l bg-sidebar transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
                    "xl:static xl:z-auto xl:translate-x-0",
                    open ? "translate-x-0" : "translate-x-full xl:translate-x-0"
                )}
            >
                <div className="flex h-14 shrink-0 items-center gap-1 border-b px-3">
                    <div className="flex flex-1 items-center gap-0.5 rounded-lg bg-muted/70 p-0.5">
                        <button
                            type="button"
                            onClick={() => onTabChange("sources")}
                            className={cn(
                                "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-medium transition-colors",
                                tab === "sources"
                                    ? "bg-card text-foreground shadow-sm"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <FileText className="size-3.5" />
                            引用
                            {sources.length > 0 && (
                                <span className="rounded-full bg-muted px-1.5 text-[10px] tabular-nums">{sources.length}</span>
                            )}
                        </button>
                        <button
                            type="button"
                            onClick={() => onTabChange("trace")}
                            className={cn(
                                "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-medium transition-colors",
                                tab === "trace"
                                    ? "bg-card text-foreground shadow-sm"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <GitBranch className="size-3.5" />
                            轨迹
                        </button>
                    </div>

                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground xl:hidden"
                        aria-label="关闭检查器"
                    >
                        <X className="size-4" />
                    </button>
                </div>

                <div className="scroll-slim min-h-0 flex-1 overflow-y-auto">
                    {tab === "sources" ? (
                        <div className="p-3">
                            {sources.length === 0 ? (
                                <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
                                    <div className="mb-3 flex size-9 items-center justify-center rounded-xl border bg-card">
                                        <FileText className="size-4 text-muted-foreground" />
                                    </div>
                                    <p className="text-xs font-medium">本轮还没有引用</p>
                                    <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                                        问一个知识库里有的问题，
                                        <br />
                                        回答里的 [1] 会在这里展开。
                                    </p>
                                </div>
                            ) : (
                                <ul className="space-y-2.5">
                                    {sources.map((source, index) => {
                                        const active = source.source_id === activeSourceId;
                                        const isOpen = expanded === source.source_id;
                                        return (
                                            <li
                                                key={source.source_id}
                                                id={`source-${source.source_id}`}
                                                className={cn(
                                                    "rounded-xl border bg-card p-3 transition-colors",
                                                    active && "border-primary/50 ring-2 ring-primary/10"
                                                )}
                                            >
                                                <button
                                                    type="button"
                                                    onClick={() => onSelectSource(source.source_id)}
                                                    className="w-full text-left"
                                                >
                                                    <div className="flex items-start gap-2">
                                                        <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md bg-muted text-[10px] font-semibold tabular-nums text-muted-foreground">
                                                            {index + 1}
                                                        </span>
                                                        <div className="min-w-0 flex-1">
                                                            <p className="truncate text-[11px] font-medium">
                                                                {source.clause_name}
                                                            </p>
                                                            <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
                                                                {source.section_path || "正文"}
                                                            </p>
                                                        </div>
                                                    </div>

                                                    <p
                                                        className={cn(
                                                            "mt-2 text-[11px] leading-relaxed text-muted-foreground",
                                                            !isOpen && "line-clamp-3"
                                                        )}
                                                    >
                                                        {source.content}
                                                    </p>
                                                </button>

                                                <div className="mt-2 flex items-center justify-between">
                                                    <button
                                                        type="button"
                                                        onClick={() =>
                                                            setExpanded(isOpen ? null : source.source_id)
                                                        }
                                                        className="inline-flex items-center gap-1 text-[10px] text-muted-foreground transition-colors hover:text-foreground"
                                                    >
                                                        {isOpen ? (
                                                            <Minimize2 className="size-3" />
                                                        ) : (
                                                            <Maximize2 className="size-3" />
                                                        )}
                                                        {isOpen ? "收起" : "展开原文"}
                                                    </button>
                                                </div>
                                            </li>
                                        );
                                    })}
                                </ul>
                            )}
                        </div>
                    ) : (
                        <div className="p-3">
                            {!runId ? (
                                <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
                                    <div className="mb-3 flex size-9 items-center justify-center rounded-xl border bg-card">
                                        <GitBranch className="size-4 text-muted-foreground" />
                                    </div>
                                    <p className="text-xs font-medium">还没有可回放的运行</p>
                                    <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                                        先发一条消息，
                                        <br />
                                        这里会出现它的每一步。
                                    </p>
                                </div>
                            ) : (
                                <>
                                    <div className="mb-3 rounded-xl border bg-card p-3">
                                        <div className="flex items-center gap-2">
                                            <GitBranch className="size-3.5 text-muted-foreground" />
                                            <span className="font-mono text-[10px] text-muted-foreground">
                                                {runId.slice(0, 8)}
                                            </span>
                                            <button
                                                type="button"
                                                onClick={copyRunId}
                                                className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                                title="复制 run_id"
                                            >
                                                {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => router.push(`/traces/${runId}`)}
                                                className="ml-auto inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                            >
                                                完整轨迹
                                                <ArrowUpRight className="size-3" />
                                            </button>
                                        </div>

                                        <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                                            <div className="rounded-lg bg-muted/60 px-1 py-1.5">
                                                <p className="text-[10px] text-muted-foreground">步数</p>
                                                <p className="text-xs font-semibold tabular-nums">
                                                    {trace?.steps.length ?? "—"}
                                                </p>
                                            </div>
                                            <div className="rounded-lg bg-muted/60 px-1 py-1.5">
                                                <p className="text-[10px] text-muted-foreground">耗时</p>
                                                <p className="text-xs font-semibold tabular-nums">
                                                    {trace ? formatDuration(totals.latency) : "—"}
                                                </p>
                                            </div>
                                            <div className="rounded-lg bg-muted/60 px-1 py-1.5">
                                                <p className="text-[10px] text-muted-foreground">tokens</p>
                                                <p className="text-xs font-semibold tabular-nums">
                                                    {trace ? formatNumber(totals.prompt + totals.completion) : "—"}
                                                </p>
                                            </div>
                                        </div>
                                    </div>

                                    {traceLoading && (
                                        <div className="space-y-2">
                                            {[0, 1, 2].map((index) => (
                                                <div key={index} className="skeleton h-14 rounded-lg" />
                                            ))}
                                        </div>
                                    )}

                                    {traceError && (
                                        <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-[11px] text-destructive">
                                            {traceError}
                                        </p>
                                    )}

                                    {!traceLoading && !traceError && trace && <TraceTimeline steps={trace.steps} />}
                                </>
                            )}
                        </div>
                    )}
                </div>
            </aside>
        </>
    );
}
