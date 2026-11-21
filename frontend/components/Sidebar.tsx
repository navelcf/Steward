"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    BookOpen,
    Check,
    Loader2,
    LogOut,
    MessageSquare,
    Pencil,
    Plus,
    Search,
    Trash2,
    X,
} from "lucide-react";
import BrandMark from "./BrandMark";
import ThemeToggle from "./ThemeToggle";
import type { Thread, User } from "@/lib/types";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/cn";

type Props = {
    threads: Thread[];
    activeId: string | null;
    loading: boolean;
    user: User | null;
    open: boolean;
    streaming?: boolean;
    onClose: () => void;
    onSelect: (id: string) => void;
    onCreate: () => Promise<void>;
    onDelete: (id: string) => Promise<void>;
    onRename: (id: string, title: string) => Promise<void>;
    onLogout: () => void;
};

export default function Sidebar({
    threads,
    activeId,
    loading,
    user,
    open,
    streaming,
    onClose,
    onSelect,
    onCreate,
    onDelete,
    onRename,
    onLogout,
}: Props) {
    const pathname = usePathname();
    const [query, setQuery] = useState("");
    const [creating, setCreating] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [draft, setDraft] = useState("");
    const [confirmId, setConfirmId] = useState<string | null>(null);

    const filtered = useMemo(() => {
        const keyword = query.trim().toLowerCase();
        if (!keyword) return threads;
        return threads.filter((thread) => thread.title.toLowerCase().includes(keyword));
    }, [threads, query]);

    async function submitRename(id: string) {
        const title = draft.trim();
        setEditingId(null);
        if (!title) return;
        await onRename(id, title);
    }

    return (
        <>
            {/* 移动端遮罩 */}
            {open && (
                <div
                    className="fixed inset-0 z-30 bg-foreground/25 backdrop-blur-[2px] lg:hidden"
                    onClick={onClose}
                    aria-hidden
                />
            )}

            <aside
                className={cn(
                    "fixed inset-y-0 left-0 z-40 flex w-[268px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
                    "lg:static lg:z-auto lg:translate-x-0",
                    open ? "translate-x-0" : "-translate-x-full"
                )}
            >
                <div className="flex items-center gap-2.5 px-4 pb-3 pt-4">
                    <BrandMark className="size-8" />
                    <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold tracking-tight">Steward</p>
                        <p className="truncate text-[10px] text-muted-foreground">可控 · 可回放的 AI 工作台</p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
                        aria-label="关闭侧栏"
                    >
                        <X className="size-4" />
                    </button>
                </div>

                <div className="px-3">
                    <button
                        type="button"
                        onClick={async () => {
                            setCreating(true);
                            try {
                                await onCreate();
                            } finally {
                                setCreating(false);
                            }
                        }}
                        disabled={creating}
                        className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-transform active:scale-[0.99] disabled:opacity-60"
                    >
                        {creating ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                        新建会话
                    </button>
                </div>

                <div className="px-3 pt-3">
                    <div className="flex items-center gap-1.5 rounded-lg border bg-card px-2 py-1.5">
                        <Search className="size-3.5 shrink-0 text-muted-foreground" />
                        <input
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            placeholder="搜索会话"
                            className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground/70"
                        />
                        {query && (
                            <button
                                type="button"
                                onClick={() => setQuery("")}
                                className="text-muted-foreground hover:text-foreground"
                                aria-label="清空搜索"
                            >
                                <X className="size-3" />
                            </button>
                        )}
                    </div>
                </div>

                <div className="flex items-center justify-between px-4 pb-1.5 pt-4 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                    <span>会话</span>
                    <span className="tabular-nums">{threads.length}</span>
                </div>

                <nav className="scroll-slim min-h-0 flex-1 overflow-y-auto px-2 pb-3">
                    {loading && (
                        <div className="space-y-2 px-1 pt-1">
                            {[0, 1, 2, 3].map((index) => (
                                <div key={index} className="skeleton h-11 rounded-lg" />
                            ))}
                        </div>
                    )}

                    {!loading && filtered.length === 0 && (
                        <p className="px-3 py-6 text-xs leading-relaxed text-muted-foreground">
                            {threads.length === 0 ? (
                                <>
                                    还没有会话。
                                    <br />
                                    点上面的「新建会话」，或者直接在右边提问。
                                </>
                            ) : (
                                <>没有匹配「{query}」的会话。</>
                            )}
                        </p>
                    )}

                    <ul className="space-y-1">
                        {filtered.map((thread) => {
                            const active = thread.id === activeId;
                            const editing = editingId === thread.id;

                            return (
                                <li key={thread.id} className="group relative">
                                    {editing ? (
                                        <div className="flex items-center gap-1 rounded-lg border bg-card px-1.5 py-1">
                                            <input
                                                autoFocus
                                                value={draft}
                                                onChange={(event) => setDraft(event.target.value)}
                                                onKeyDown={(event) => {
                                                    if (event.key === "Enter") {
                                                        event.preventDefault();
                                                        void submitRename(thread.id);
                                                    }
                                                    if (event.key === "Escape") setEditingId(null);
                                                }}
                                                className="min-w-0 flex-1 bg-transparent px-1 text-xs outline-none"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => void submitRename(thread.id)}
                                                className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                                                aria-label="保存标题"
                                            >
                                                <Check className="size-3.5" />
                                            </button>
                                        </div>
                                    ) : (
                                        <button
                                            type="button"
                                            onClick={() => onSelect(thread.id)}
                                            className={cn(
                                                "flex w-full items-start gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors",
                                                active
                                                    ? "border-border bg-card text-foreground shadow-sm"
                                                    : "border-transparent text-muted-foreground hover:bg-accent/70 hover:text-foreground"
                                            )}
                                        >
                                            <MessageSquare
                                                className={cn(
                                                    "mt-0.5 size-3.5 shrink-0",
                                                    active ? "text-foreground" : "text-muted-foreground/70"
                                                )}
                                            />
                                            <span className="min-w-0 flex-1">
                                                <span className="block truncate text-xs font-medium">{thread.title}</span>
                                                <span className="mt-0.5 block text-[10px] text-muted-foreground/70">
                                                    {formatRelative(thread.updated_at)}
                                                    {streaming && active ? " · 生成中" : ""}
                                                </span>
                                            </span>
                                        </button>
                                    )}

                                    {!editing && confirmId !== thread.id && (
                                        <div className="absolute right-1 top-1.5 flex items-center gap-0.5 opacity-100 transition-opacity lg:opacity-0 lg:group-hover:opacity-100">
                                            <button
                                                type="button"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    setEditingId(thread.id);
                                                    setDraft(thread.title);
                                                }}
                                                title="重命名"
                                                className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                                            >
                                                <Pencil className="size-3" />
                                            </button>
                                            <button
                                                type="button"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    setConfirmId(thread.id);
                                                }}
                                                title="删除会话"
                                                className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                                            >
                                                <Trash2 className="size-3" />
                                            </button>
                                        </div>
                                    )}

                                    {confirmId === thread.id && (
                                        <div className="absolute inset-0 z-10 flex items-center justify-between gap-2 rounded-lg border border-destructive/30 bg-card px-2.5 text-[11px] shadow-sm">
                                            <span className="truncate text-muted-foreground">删除这个会话？</span>
                                            <span className="flex shrink-0 items-center gap-1">
                                                <button
                                                    type="button"
                                                    onClick={async () => {
                                                        setConfirmId(null);
                                                        await onDelete(thread.id);
                                                    }}
                                                    className="rounded bg-destructive px-1.5 py-0.5 font-medium text-destructive-foreground"
                                                >
                                                    删除
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setConfirmId(null)}
                                                    className="rounded px-1.5 py-0.5 text-muted-foreground hover:bg-accent"
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
                </nav>

                <div className="border-t border-sidebar-border px-3 py-3">
                    <Link
                        href="/knowledge"
                        onClick={onClose}
                        className={cn(
                            "flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors",
                            pathname.startsWith("/knowledge")
                                ? "bg-card text-foreground shadow-sm"
                                : "text-muted-foreground hover:bg-accent/70 hover:text-foreground"
                        )}
                    >
                        <BookOpen className="size-3.5" />
                        知识库
                        <span className="ml-auto text-[10px] text-muted-foreground/60">RAG</span>
                    </Link>

                    <div className="mt-2 flex items-center gap-2 rounded-lg border bg-card px-2 py-1.5">
                        <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
                            {(user?.display_name || user?.email || "?").slice(0, 1).toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-[11px] font-medium">{user?.display_name || user?.email || "加载中…"}</p>
                            <p className="truncate text-[10px] text-muted-foreground">
                                {user?.display_name ? user.email : "已登录"}
                            </p>
                        </div>
                        <ThemeToggle className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground" />
                        <button
                            type="button"
                            onClick={onLogout}
                            title="退出登录"
                            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                        >
                            <LogOut className="size-3.5" />
                        </button>
                    </div>
                </div>
            </aside>
        </>
    );
}
