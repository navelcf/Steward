"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
    AlertCircle,
    ArrowLeft,
    BookOpen,
    CheckCircle2,
    Database,
    FileText,
    HardDrive,
    Loader2,
    Search,
    Trash2,
    Type,
    UploadCloud,
    X,
} from "lucide-react";
import BrandMark from "@/components/BrandMark";
import ThemeToggle from "@/components/ThemeToggle";
import { deleteDocument, getToken, listDocuments, searchKnowledge, uploadDocument } from "@/lib/api";
import { formatBytes, formatDateTime, formatNumber, suffixOf } from "@/lib/format";
import { cn } from "@/lib/cn";
import type { DocumentRow, SearchHit } from "@/lib/types";

const ACCEPT = ".pdf,.docx,.md,.txt";
const MAX_BYTES = 20 * 1024 * 1024;

function statusOf(doc: DocumentRow) {
    if (doc.is_indexed) {
        return { label: "已索引", className: "border-success/30 bg-success/10 text-success" };
    }
    if (doc.status === "failed") {
        return { label: "失败", className: "border-destructive/30 bg-destructive/10 text-destructive" };
    }
    return { label: "处理中", className: "border-waiting/40 bg-waiting/10 text-waiting-foreground" };
}

export default function KnowledgePage() {
    const router = useRouter();
    const inputRef = useRef<HTMLInputElement>(null);

    const [docs, setDocs] = useState<DocumentRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const [uploading, setUploading] = useState(false);
    const [uploadName, setUploadName] = useState("");
    const [dragging, setDragging] = useState(false);
    const [confirmId, setConfirmId] = useState<string | null>(null);

    const [query, setQuery] = useState("");
    const [searching, setSearching] = useState(false);
    const [hits, setHits] = useState<SearchHit[] | null>(null);
    const [searchError, setSearchError] = useState("");

    useEffect(() => {
        if (!getToken()) router.replace("/login");
    }, [router]);

    const refresh = useCallback(async () => {
        const rows = await listDocuments();
        setDocs(rows);
    }, []);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const rows = await listDocuments();
                if (!cancelled) setDocs(rows);
            } catch (err) {
                if (!cancelled) setError(err instanceof Error ? err.message : "加载文档失败");
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    const stats = useMemo(() => {
        const indexed = docs.filter((doc) => doc.is_indexed).length;
        const chars = docs.reduce((sum, doc) => sum + (doc.char_count ?? 0), 0);
        const bytes = docs.reduce((sum, doc) => sum + doc.size_bytes, 0);
        return { indexed, chars, bytes };
    }, [docs]);

    const nameById = useMemo(() => new Map(docs.map((doc) => [doc.id, doc.filename])), [docs]);

    const handleFiles = useCallback(
        async (file: File | undefined) => {
            if (!file || uploading) return;
            if (!ACCEPT.split(",").some((suffix) => file.name.toLowerCase().endsWith(suffix))) {
                setError("只支持 PDF / DOCX / MD / TXT");
                return;
            }
            if (file.size > MAX_BYTES) {
                setError("文件超过 20MB，请拆分后再上传");
                return;
            }

            setUploading(true);
            setUploadName(file.name);
            setError("");
            try {
                await uploadDocument(file);
                await refresh();
            } catch (err) {
                setError(err instanceof Error ? err.message : "上传失败");
            } finally {
                setUploading(false);
                setUploadName("");
            }
        },
        [refresh, uploading]
    );

    async function handleSearch() {
        const text = query.trim();
        if (!text || searching) return;
        setSearching(true);
        setSearchError("");
        try {
            const data = await searchKnowledge(text, 20);
            setHits(data.hits);
        } catch (err) {
            setSearchError(err instanceof Error ? err.message : "检索失败");
            setHits(null);
        } finally {
            setSearching(false);
        }
    }

    async function handleDelete(id: string) {
        setConfirmId(null);
        try {
            await deleteDocument(id);
            setDocs((prev) => prev.filter((doc) => doc.id !== id));
        } catch (err) {
            setError(err instanceof Error ? err.message : "删除失败");
        }
    }

    const topScore = hits && hits.length > 0 ? hits[0].score : 0;

    return (
        <main className="min-h-[100dvh] bg-background">
            <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur-md">
                <div className="mx-auto flex h-14 max-w-5xl items-center gap-3 px-4">
                    <Link
                        href="/"
                        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                    >
                        <ArrowLeft className="size-3.5" />
                        返回对话
                    </Link>
                    <span className="h-4 w-px bg-border" />
                    <BrandMark className="size-7" />
                    <div className="min-w-0 flex-1">
                        <h1 className="truncate text-sm font-semibold tracking-tight">知识库</h1>
                        <p className="truncate text-[10px] text-muted-foreground">
                            上传文档 → 自动切片入 Milvus → 对话里可被检索与引用
                        </p>
                    </div>
                    <ThemeToggle />
                </div>
            </header>

            <div className="mx-auto max-w-5xl space-y-5 px-4 py-6">
                {error && (
                    <div className="flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                        <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
                        <span className="flex-1 leading-relaxed">{error}</span>
                        <button
                            type="button"
                            onClick={() => setError("")}
                            className="rounded p-0.5 hover:bg-destructive/10"
                            aria-label="关闭"
                        >
                            <X className="size-3.5" />
                        </button>
                    </div>
                )}

                {/* 概览 */}
                <section className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {[
                        { icon: BookOpen, label: "文档", value: formatNumber(docs.length) },
                        { icon: CheckCircle2, label: "已索引", value: formatNumber(stats.indexed) },
                        { icon: Type, label: "总字数", value: formatNumber(stats.chars) },
                        { icon: HardDrive, label: "占用", value: formatBytes(stats.bytes) },
                    ].map((item) => {
                        const Icon = item.icon;
                        return (
                            <div key={item.label} className="rounded-xl border bg-card px-3 py-2.5">
                                <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                                    <Icon className="size-3" />
                                    {item.label}
                                </div>
                                <p className="mt-1 text-lg font-semibold tabular-nums tracking-tight">{item.value}</p>
                            </div>
                        );
                    })}
                </section>

                {/* 上传 */}
                <section
                    onDragOver={(event) => {
                        event.preventDefault();
                        setDragging(true);
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(event) => {
                        event.preventDefault();
                        setDragging(false);
                        void handleFiles(event.dataTransfer.files?.[0]);
                    }}
                    className={cn(
                        "relative overflow-hidden rounded-2xl border border-dashed bg-card px-5 py-6 text-center transition-colors",
                        dragging ? "border-primary/50 bg-accent/50" : "hover:border-primary/30"
                    )}
                >
                    <input
                        ref={inputRef}
                        type="file"
                        accept={ACCEPT}
                        className="hidden"
                        onChange={(event) => {
                            void handleFiles(event.target.files?.[0]);
                            event.target.value = "";
                        }}
                    />

                    {uploading ? (
                        <div className="flex flex-col items-center gap-2 py-2">
                            <Loader2 className="size-6 animate-spin text-muted-foreground" />
                            <p className="max-w-md truncate text-xs font-medium">{uploadName}</p>
                            <p className="text-[11px] text-muted-foreground">
                                正在解析、切片、向量化 —— 同步执行，大文件可能要十几秒。
                            </p>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center gap-2">
                            <div className="flex size-10 items-center justify-center rounded-xl border bg-muted/60">
                                <UploadCloud className="size-5 text-muted-foreground" />
                            </div>
                            <p className="text-sm font-medium">把文档拖进来，或点击选择</p>
                            <p className="text-[11px] text-muted-foreground">
                                支持 PDF / DOCX / MD / TXT，单个不超过 20MB
                            </p>
                            <button
                                type="button"
                                onClick={() => inputRef.current?.click()}
                                className="mt-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow-sm transition-transform active:scale-[0.98]"
                            >
                                选择文件
                            </button>
                        </div>
                    )}
                </section>

                {/* 检索 */}
                <section className="rounded-2xl border bg-card p-4">
                    <div className="flex items-center gap-2">
                        <div className="flex flex-1 items-center gap-2 rounded-lg border bg-background px-2.5 py-1.5">
                            <Search className="size-3.5 shrink-0 text-muted-foreground" />
                            <input
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                                onKeyDown={(event) => {
                                    if (event.key === "Enter" && !event.nativeEvent.isComposing) {
                                        event.preventDefault();
                                        void handleSearch();
                                    }
                                }}
                                placeholder="先在知识库里试检索一句，看看会命中哪些段落"
                                className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground/70"
                            />
                            {query && (
                                <button
                                    type="button"
                                    onClick={() => {
                                        setQuery("");
                                        setHits(null);
                                    }}
                                    className="text-muted-foreground hover:text-foreground"
                                    aria-label="清空"
                                >
                                    <X className="size-3" />
                                </button>
                            )}
                        </div>
                        <button
                            type="button"
                            onClick={() => void handleSearch()}
                            disabled={searching || !query.trim()}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground shadow-sm transition-transform active:scale-[0.98] disabled:opacity-40"
                        >
                            {searching ? <Loader2 className="size-3.5 animate-spin" /> : <Search className="size-3.5" />}
                            检索
                        </button>
                    </div>

                    {searchError && (
                        <p className="mt-3 rounded-lg border border-destructive/25 bg-destructive/5 px-3 py-2 text-[11px] text-destructive">
                            {searchError}
                        </p>
                    )}

                    {hits && (
                        <div className="mt-3">
                            <p className="mb-2 text-[11px] text-muted-foreground">
                                {hits.length > 0 ? `命中 ${hits.length} 个父块（按融合分数排序）` : "没有命中。"}
                            </p>
                            <ul className="space-y-2">
                                {hits.map((hit, index) => {
                                    const width = topScore > 0 ? Math.max(6, Math.round((hit.score / topScore) * 100)) : 0;
                                    return (
                                        <li key={hit.parent_id} className="rounded-xl border bg-background p-3">
                                            <div className="flex items-start gap-2">
                                                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md bg-muted text-[10px] font-semibold tabular-nums text-muted-foreground">
                                                    {index + 1}
                                                </span>
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex flex-wrap items-center gap-2 text-[11px]">
                                                        <span className="truncate font-medium">
                                                            {nameById.get(hit.doc_id) ?? "未知文档"}
                                                        </span>
                                                        <span className="truncate text-muted-foreground">
                                                            {hit.section_path || "正文"}
                                                        </span>
                                                        <span className="ml-auto text-[10px] text-muted-foreground/70">
                                                            第 {index + 1} 名
                                                        </span>
                                                    </div>
                                                    <p className="mt-1.5 line-clamp-3 text-[11px] leading-relaxed text-muted-foreground">
                                                        {hit.raw_content}
                                                    </p>
                                                    <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted">
                                                        <div
                                                            className="h-full rounded-full bg-primary/60"
                                                            style={{ width: `${width}%` }}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    )}
                </section>

                {/* 文档列表 */}
                <section>
                    <div className="mb-2 flex items-center justify-between px-1">
                        <h2 className="text-xs font-medium text-muted-foreground">我的文档</h2>
                        <span className="text-[10px] text-muted-foreground/70">
                            {loading ? "加载中…" : `${docs.length} 份`}
                        </span>
                    </div>

                    {loading && (
                        <div className="space-y-2">
                            {[0, 1, 2].map((index) => (
                                <div key={index} className="skeleton h-16 rounded-xl" />
                            ))}
                        </div>
                    )}

                    {!loading && docs.length === 0 && (
                        <div className="rounded-2xl border border-dashed px-6 py-12 text-center">
                            <div className="mx-auto mb-3 flex size-9 items-center justify-center rounded-xl border bg-card">
                                <Database className="size-4 text-muted-foreground" />
                            </div>
                            <p className="text-sm font-medium">知识库还是空的</p>
                            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                                上传一份 PDF 或 DOCX，回到对话里问它里面的问题。
                            </p>
                        </div>
                    )}

                    <ul className="space-y-2">
                        {docs.map((doc) => {
                            const status = statusOf(doc);
                            const suffix = suffixOf(doc.filename).toUpperCase();
                            return (
                                <li key={doc.id} className="overflow-hidden rounded-xl border bg-card">
                                    <div className="flex items-start gap-3 p-3.5">
                                        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border bg-muted/50">
                                            <FileText className="size-4 text-muted-foreground" />
                                        </div>

                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <p className="min-w-0 truncate text-xs font-medium">{doc.filename}</p>
                                                <span
                                                    className={cn(
                                                        "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px]",
                                                        status.className
                                                    )}
                                                >
                                                    {status.label}
                                                </span>
                                                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                                    {suffix || "FILE"}
                                                </span>
                                            </div>

                                            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
                                                <span>{formatBytes(doc.size_bytes)}</span>
                                                <span className="text-muted-foreground/40">·</span>
                                                <span>{doc.page_count ? `${doc.page_count} 页` : "无分页"}</span>
                                                <span className="text-muted-foreground/40">·</span>
                                                <span>{formatNumber(doc.char_count)} 字</span>
                                                <span className="text-muted-foreground/40">·</span>
                                                <span>{formatDateTime(doc.created_at)}</span>
                                                {doc.parser && (
                                                    <>
                                                        <span className="text-muted-foreground/40">·</span>
                                                        <span>{doc.parser}</span>
                                                    </>
                                                )}
                                            </p>

                                            {doc.error_message && (
                                                <p className="mt-1.5 rounded-md bg-destructive/5 px-2 py-1 text-[10px] text-destructive">
                                                    {doc.error_message}
                                                </p>
                                            )}
                                        </div>

                                        <button
                                            type="button"
                                            onClick={() => setConfirmId(doc.id)}
                                            title="删除文档"
                                            className="shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                                        >
                                            <Trash2 className="size-3.5" />
                                        </button>
                                    </div>

                                    {confirmId === doc.id && (
                                        <div className="flex items-center justify-between gap-2 border-t border-destructive/20 bg-destructive/5 px-3.5 py-2 text-[11px]">
                                            <span className="truncate text-destructive">删除后会同时清掉它的所有向量块。</span>
                                            <span className="flex shrink-0 items-center gap-1.5">
                                                <button
                                                    type="button"
                                                    onClick={() => void handleDelete(doc.id)}
                                                    className="rounded bg-destructive px-2 py-0.5 font-medium text-destructive-foreground"
                                                >
                                                    删除
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setConfirmId(null)}
                                                    className="rounded px-2 py-0.5 text-muted-foreground hover:bg-accent"
                                                >
                                                    取消
                                                </button>
                                            </span>
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                </section>
            </div>
        </main>
    );
}
