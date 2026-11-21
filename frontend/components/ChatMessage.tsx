"use client";

import { useEffect, useState } from "react";
import { Check, Copy, FileText, GitBranch, Loader2, UserRound } from "lucide-react";
import BrandMark from "./BrandMark";
import Markdown from "./Markdown";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { formatClock, formatElapsed } from "@/lib/format";
import { normalizeSources } from "@/lib/api";
import { cn } from "@/lib/cn";

type Props = {
    message: ChatMessageType;
    activeSourceId?: string | null;
    onCite?: (sourceId: string) => void;
    onOpenSources?: (message: ChatMessageType) => void;
    onOpenTrace?: (runId: string) => void;
};

// 计时器：只在「思考中」这一段挂载，避免整页每秒重渲染。
function ThinkingRow({ startedAt }: { startedAt: number }) {
    const [elapsed, setElapsed] = useState(() => formatElapsed(startedAt));

    useEffect(() => {
        const timer = window.setInterval(() => setElapsed(formatElapsed(startedAt)), 200);
        return () => window.clearInterval(timer);
    }, [startedAt]);

    return (
        <div className="flex items-center gap-2.5 py-0.5 text-sm text-muted-foreground">
            <span className="flex items-end gap-1">
                <span className="thinking-dot size-1.5 rounded-full bg-current" />
                <span className="thinking-dot size-1.5 rounded-full bg-current" />
                <span className="thinking-dot size-1.5 rounded-full bg-current" />
            </span>
            <span className="sheen">正在检索与思考</span>
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground/70">{elapsed}</span>
        </div>
    );
}

export default function ChatMessage({ message, activeSourceId, onCite, onOpenSources, onOpenTrace }: Props) {
    const [copied, setCopied] = useState(false);
    const sources = normalizeSources(message.sources);
    const isUser = message.role === "user";
    const isSystem = message.role === "system";

    async function copy() {
        try {
            await navigator.clipboard.writeText(message.content);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1600);
        } catch {
            // 没权限就算了
        }
    }

    if (isSystem) {
        return (
            <div className="fade-up flex justify-center py-1">
                <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-[11px] text-muted-foreground shadow-sm">
                    <span className="size-1.5 rounded-full bg-waiting" />
                    {message.content}
                </span>
            </div>
        );
    }

    if (isUser) {
        return (
            <div className="fade-up flex justify-end gap-3">
                <div className="flex max-w-[min(680px,86%)] flex-col items-end gap-1">
                    <div className="rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground shadow-sm">
                        <p className="whitespace-pre-wrap break-words">{message.content}</p>
                    </div>
                    <span className="pr-1 text-[10px] text-muted-foreground/70">{formatClock(message.created_at)}</span>
                </div>
                <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full border bg-card text-muted-foreground">
                    <UserRound className="size-3.5" />
                </div>
            </div>
        );
    }

    return (
        <div className="fade-up group flex gap-3">
            <BrandMark className="mt-0.5 size-7" />

            <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                    <span className="font-medium text-foreground/80">Steward</span>
                    <span>{formatClock(message.created_at)}</span>
                    {message.streaming && (
                        <span className="inline-flex items-center gap-1 text-running">
                            <Loader2 className="size-3 animate-spin" />
                            生成中
                        </span>
                    )}
                    {message.waiting && (
                        <span className="inline-flex items-center gap-1 text-waiting-foreground">
                            <span className="size-1.5 rounded-full bg-waiting" />
                            等待确认
                        </span>
                    )}
                </div>

                <div className="rounded-2xl rounded-tl-md border bg-card px-4 py-3 text-card-foreground shadow-[0_1px_2px_rgb(0_0_0/0.03)]">
                    {message.streaming && !message.content && message.startedAt !== undefined ? (
                        <ThinkingRow startedAt={message.startedAt} />
                    ) : (
                        <div className={cn(message.streaming && "stream-caret")}>
                            <Markdown
                                content={message.content}
                                sources={sources}
                                activeSourceId={activeSourceId}
                                onCite={onCite}
                            />
                        </div>
                    )}

                    {message.waiting && !message.content && (
                        <p className="mt-2 text-xs text-muted-foreground">
                            工具调用需要你确认后才会继续，按钮在下方。
                        </p>
                    )}
                </div>

                <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                    {sources.length > 0 && (
                        <button
                            type="button"
                            onClick={() => onOpenSources?.(message)}
                            className="inline-flex items-center gap-1 rounded-full border bg-card px-2 py-0.5 transition-colors hover:bg-accent hover:text-foreground"
                        >
                            <FileText className="size-3" />
                            引用 {sources.length}
                        </button>
                    )}

                    <button
                        type="button"
                        onClick={copy}
                        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 opacity-100 transition-colors hover:bg-accent hover:text-foreground sm:opacity-0 sm:group-hover:opacity-100"
                    >
                        {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
                        {copied ? "已复制" : "复制"}
                    </button>

                    {message.run_id && (
                        <button
                            type="button"
                            onClick={() => onOpenTrace?.(message.run_id as string)}
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 opacity-100 transition-colors hover:bg-accent hover:text-foreground sm:opacity-0 sm:group-hover:opacity-100"
                        >
                            <GitBranch className="size-3" />
                            轨迹
                        </button>
                    )}

                    {sources.length > 0 && (
                        <span className="hidden items-center gap-1 sm:inline-flex">
                            {sources.slice(0, 2).map((source, index) => (
                                <button
                                    key={source.source_id}
                                    type="button"
                                    onClick={() => onCite?.(source.source_id)}
                                    className="max-w-[180px] truncate rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                    title={`${source.clause_name} · ${source.section_path}`}
                                >
                                    [{index + 1}] {source.clause_name}
                                </button>
                            ))}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}
