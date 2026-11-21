"use client";

import { AlertTriangle, Bot, ChevronRight, ShieldCheck, Wrench } from "lucide-react";
import type { TraceStep } from "@/lib/types";
import { formatClock, formatDuration, formatNumber } from "@/lib/format";
import { cn } from "@/lib/cn";

const KIND_META: Record<string, { label: string; icon: typeof Bot; tone: string }> = {
    model: { label: "模型调用", icon: Bot, tone: "text-running" },
    tool: { label: "工具调用", icon: Wrench, tone: "text-foreground" },
    approval: { label: "审批", icon: ShieldCheck, tone: "text-waiting-foreground" },
    error: { label: "错误", icon: AlertTriangle, tone: "text-destructive" },
};

function metaOf(kind: string) {
    return KIND_META[kind] ?? { label: kind, icon: Bot, tone: "text-muted-foreground" };
}

function stringify(value: unknown): string {
    if (value === null || value === undefined) return "";
    try {
        const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
        return text.length > 4000 ? `${text.slice(0, 4000)}\n…（已截断）` : text;
    } catch {
        return String(value);
    }
}

export default function TraceTimeline({ steps }: { steps: TraceStep[] }) {
    if (steps.length === 0) {
        return (
            <p className="rounded-xl border border-dashed px-4 py-8 text-center text-xs text-muted-foreground">
                这次运行没有留下轨迹。
            </p>
        );
    }

    return (
        <ol className="space-y-0">
            {steps.map((step, index) => {
                const meta = metaOf(step.kind);
                const Icon = meta.icon;
                const last = index === steps.length - 1;
                const input = stringify(step.input);
                const output = stringify(step.output);
                // 模型步骤的 name 是 LangChain 的类名（AIMessage），对用户没意义，统一叫「模型回复」。
                const title = step.kind === "model" ? "模型回复" : step.name || meta.label;

                return (
                    <li key={`${step.step}-${index}`} className="flex gap-3">
                        <div className="flex w-7 shrink-0 flex-col items-center">
                            <div
                                className={cn(
                                    "z-10 flex size-7 items-center justify-center rounded-full border bg-card shadow-sm",
                                    step.kind === "error" && "border-destructive/40"
                                )}
                            >
                                <Icon className={cn("size-3.5", meta.tone)} />
                            </div>
                            {!last && <div className="w-px flex-1 bg-border" />}
                        </div>

                        <div className={cn("min-w-0 flex-1", last ? "pb-0" : "pb-4")}>
                            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                                <span className="text-[10px] font-mono text-muted-foreground">
                                    #{String(step.step).padStart(2, "0")}
                                </span>
                                <span className="text-xs font-medium">{title}</span>
                                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                    {meta.label}
                                </span>
                                <span className="text-[10px] tabular-nums text-muted-foreground">
                                    {formatDuration(step.latency_ms)}
                                </span>
                                {(step.prompt_tokens !== null || step.completion_tokens !== null) && (
                                    <span className="text-[10px] tabular-nums text-muted-foreground">
                                        ↑{formatNumber(step.prompt_tokens)} ↓{formatNumber(step.completion_tokens)}
                                    </span>
                                )}
                                <span className="ml-auto text-[10px] text-muted-foreground/70">
                                    {formatClock(step.created_at)}
                                </span>
                            </div>

                            {(input || output) && (
                                <details className="group mt-1.5 rounded-lg border bg-card/60">
                                    <summary className="flex cursor-pointer list-none items-center gap-1 px-2.5 py-1.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground">
                                        <ChevronRight className="size-3 transition-transform group-open:rotate-90" />
                                        输入 / 输出
                                    </summary>
                                    <div className="space-y-2 border-t px-2.5 py-2">
                                        {input && (
                                            <div>
                                                <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                                                    输入
                                                </p>
                                                <pre className="scroll-slim max-h-56 overflow-auto rounded bg-muted/50 p-2 font-mono text-[10px] leading-relaxed whitespace-pre-wrap break-words">
                                                    {input}
                                                </pre>
                                            </div>
                                        )}
                                        {output && (
                                            <div>
                                                <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                                                    输出
                                                </p>
                                                <pre className="scroll-slim max-h-56 overflow-auto rounded bg-muted/50 p-2 font-mono text-[10px] leading-relaxed whitespace-pre-wrap break-words">
                                                    {output}
                                                </pre>
                                            </div>
                                        )}
                                    </div>
                                </details>
                            )}
                        </div>
                    </li>
                );
            })}
        </ol>
    );
}
