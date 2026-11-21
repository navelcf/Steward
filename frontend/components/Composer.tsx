"use client";

import { useRef, useState } from "react";
import { ArrowUp, FileText, Loader2, Paperclip, Square, X } from "lucide-react";
import type { UploadedFile } from "@/lib/types";
import { formatBytes, formatNumber } from "@/lib/format";
import { cn } from "@/lib/cn";

type Props = {
    value: string;
    onChange: (value: string) => void;
    onSend: () => void;
    streaming?: boolean;
    disabled?: boolean;
    attachment: UploadedFile | null;
    attaching?: boolean;
    onAttach: (file: File) => void;
    onRemoveAttachment: () => void;
    onStop: () => void;
    placeholder?: string;
};

const ACCEPT = ".pdf,.docx,.md,.txt";

export default function Composer({
    value,
    onChange,
    onSend,
    streaming,
    disabled,
    attachment,
    attaching,
    onAttach,
    onRemoveAttachment,
    onStop,
    placeholder,
}: Props) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const [dragging, setDragging] = useState(false);

    const canSend = !disabled && !streaming && !attaching && value.trim().length > 0;

    function submit() {
        if (!canSend) return;
        onSend();
        if (textareaRef.current) textareaRef.current.style.height = "auto";
    }

    function pick(file: File | undefined) {
        if (!file) return;
        onAttach(file);
    }

    return (
        <div className="border-t bg-background/80 px-3 py-3 backdrop-blur-md sm:px-5">
            <div
                onDragOver={(event) => {
                    event.preventDefault();
                    setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                    event.preventDefault();
                    setDragging(false);
                    pick(event.dataTransfer.files?.[0]);
                }}
                className={cn(
                    "mx-auto flex max-w-3xl flex-col gap-2 rounded-2xl border bg-card p-2 shadow-sm transition-shadow focus-within:shadow-md",
                    dragging && "border-primary/50 ring-2 ring-primary/10"
                )}
            >
                {attachment && (
                    <div className="mx-1 mt-0.5 flex items-center gap-2 rounded-lg border bg-muted/60 px-2.5 py-1.5 text-xs">
                        <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 flex-1 truncate font-medium">{attachment.filename}</span>
                        <span className="shrink-0 text-[10px] text-muted-foreground">
                            {formatBytes(attachment.size)} · 约 {formatNumber(attachment.token_estimate)} tokens
                        </span>
                        <button
                            type="button"
                            onClick={onRemoveAttachment}
                            title="移除附件"
                            className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                        >
                            <X className="size-3.5" />
                        </button>
                    </div>
                )}

                <div className="flex items-end gap-1.5">
                    <input
                        ref={inputRef}
                        type="file"
                        accept={ACCEPT}
                        className="hidden"
                        onChange={(event) => {
                            pick(event.target.files?.[0]);
                            event.target.value = "";
                        }}
                    />
                    <button
                        type="button"
                        onClick={() => inputRef.current?.click()}
                        disabled={streaming || attaching}
                        title="附加文档（PDF / DOCX / MD / TXT，≤ 20MB）"
                        className="mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40"
                    >
                        {attaching ? <Loader2 className="size-4 animate-spin" /> : <Paperclip className="size-4" />}
                    </button>

                    <textarea
                        ref={textareaRef}
                        rows={1}
                        value={value}
                        disabled={disabled}
                        onChange={(event) => {
                            onChange(event.target.value);
                            const el = event.currentTarget;
                            el.style.height = "auto";
                            el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
                        }}
                        onKeyDown={(event) => {
                            // 中文输入法还在选词时按 Enter 是确认候选，不能发送。
                            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                                event.preventDefault();
                                submit();
                            }
                        }}
                        placeholder={placeholder ?? "问点什么，或把文档里的问题丢进来…"}
                        className="max-h-[160px] flex-1 resize-none bg-transparent px-1.5 py-1.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/70 disabled:opacity-60"
                    />

                    {streaming ? (
                        <button
                            type="button"
                            onClick={onStop}
                            title="停止生成"
                            className="mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                        >
                            <Square className="size-3 fill-current" />
                        </button>
                    ) : (
                        <button
                            type="button"
                            onClick={submit}
                            disabled={!canSend}
                            title="发送（Enter）"
                            className="mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform active:scale-95 disabled:opacity-30"
                        >
                            <ArrowUp className="size-4" />
                        </button>
                    )}
                </div>
            </div>

            <p className="mx-auto mt-1.5 flex max-w-3xl items-center gap-2 px-1 text-[10px] text-muted-foreground">
                <span>Enter 发送 · Shift + Enter 换行</span>
                <span className="text-muted-foreground/40">·</span>
                <span>附件会随本轮问题一起读入</span>
            </p>
        </div>
    );
}
