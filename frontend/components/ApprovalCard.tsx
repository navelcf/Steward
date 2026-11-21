"use client";

import { useState } from "react";
import { Check, ChevronDown, Loader2, ShieldAlert, X } from "lucide-react";
import type { ApprovalCardData } from "@/lib/types";
import { formatExpiry, isExpired } from "@/lib/format";
import { toolLabel } from "@/lib/tools";
import { cn } from "@/lib/cn";

type Props = {
    card: ApprovalCardData;
    busy?: boolean;
    onDecide: (decision: "approve" | "reject", note?: string) => void;
};

export default function ApprovalCard({ card, busy, onDecide }: Props) {
    const [note, setNote] = useState("");
    const [showNote, setShowNote] = useState(false);
    const expired = isExpired(card.expires_at);
    const label = toolLabel(card.tool_name);
    const args = Object.keys(card.args ?? {}).length > 0 ? JSON.stringify(card.args, null, 2) : "";

    return (
        <div
            className={cn(
                "fade-up overflow-hidden rounded-2xl border bg-card shadow-md",
                expired ? "opacity-70" : "approval-breathe"
            )}
        >
            <div className="h-1 w-full bg-waiting" />

            <div className="px-4 py-3.5">
                <div className="flex items-start gap-2.5">
                    <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-waiting/15 text-waiting-foreground">
                        <ShieldAlert className="size-4" />
                    </div>

                    <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold tracking-tight">
                                {expired ? "审批已过期" : "这个操作需要你确认"}
                            </h3>
                            <span className="rounded-full border border-waiting/40 bg-waiting/10 px-2 py-0.5 text-[10px] font-medium text-waiting-foreground">
                                {label}
                            </span>
                            <span className="ml-auto text-[10px] text-muted-foreground">
                                {formatExpiry(card.expires_at)}
                            </span>
                        </div>

                        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                            模型请求执行 <code className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{card.tool_name}</code>
                            {card.risk_note ? `：${card.risk_note}` : "。确认后才会真正执行。"}
                        </p>
                    </div>
                </div>

                {args && (
                    <div className="mt-3">
                        <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                            参数
                        </p>
                        <pre className="scroll-slim max-h-40 overflow-auto rounded-lg border bg-muted/50 px-3 py-2 font-mono text-[11px] leading-relaxed">
                            {args}
                        </pre>
                    </div>
                )}

                {showNote && (
                    <input
                        autoFocus
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                        placeholder="给模型一句话备注（可留空）"
                        maxLength={500}
                        className="mt-3 w-full rounded-lg border bg-background px-3 py-2 text-xs outline-none focus:border-primary"
                    />
                )}

                <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button
                        type="button"
                        disabled={busy || expired}
                        onClick={() => onDecide("approve", note)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow-sm transition-transform active:scale-[0.98] disabled:opacity-50"
                    >
                        {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
                        批准并继续
                    </button>

                    <button
                        type="button"
                        disabled={busy || expired}
                        onClick={() => onDecide("reject", note)}
                        className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
                    >
                        <X className="size-3.5" />
                        拒绝
                    </button>

                    <button
                        type="button"
                        onClick={() => setShowNote((value) => !value)}
                        className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                        <ChevronDown className={cn("size-3 transition-transform", showNote && "rotate-180")} />
                        备注
                    </button>
                </div>
            </div>
        </div>
    );
}
