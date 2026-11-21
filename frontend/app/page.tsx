"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
    AlertCircle,
    BookOpen,
    Menu,
    PanelRight,
    Sparkles,
    X,
} from "lucide-react";
import Sidebar from "@/components/Sidebar";
import ChatMessage from "@/components/ChatMessage";
import Composer from "@/components/Composer";
import ApprovalCard from "@/components/ApprovalCard";
import Inspector from "@/components/Inspector";
import BrandMark from "@/components/BrandMark";
import ThemeToggle from "@/components/ThemeToggle";
import {
    clearToken,
    createThread,
    deleteThread,
    decideApproval,
    getMe,
    getToken,
    listApprovals,
    listMessages,
    listThreads,
    normalizeSources,
    renameThread,
    streamChat,
    tempId,
    uploadFile,
} from "@/lib/api";
import { toolLabel } from "@/lib/tools";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/cn";
import type {
    ApprovalCardData,
    ChatMessage as ChatMessageType,
    Source,
    StreamEvent,
    Thread,
    UploadedFile,
    User,
} from "@/lib/types";

const SUGGESTIONS = [
    {
        title: "总结一份资料",
        prompt: "帮我总结知识库里最近上传的那份文档，按章节列要点，并标注出处。",
    },
    {
        title: "对比两处说法",
        prompt: "知识库里的文档对同一个问题有不同说法吗？如果有，请对比并给出引用。",
    },
    {
        title: "写条笔记",
        prompt: "把「项目周报的固定结构」整理成一条笔记保存下来。",
    },
];

function isAbortError(error: unknown): boolean {
    if (error instanceof DOMException) return error.name === "AbortError";
    return error instanceof Error && error.name === "AbortError";
}

function systemMessage(content: string): ChatMessageType {
    return {
        id: tempId(),
        role: "system",
        content,
        created_at: new Date().toISOString(),
    };
}

export default function WorkspacePage() {
    const router = useRouter();

    const [threads, setThreads] = useState<Thread[]>([]);
    const [threadsLoading, setThreadsLoading] = useState(true);
    const [activeId, setActiveId] = useState<string | null>(null);
    const [messages, setMessages] = useState<ChatMessageType[]>([]);
    const [messagesLoading, setMessagesLoading] = useState(false);
    const [streaming, setStreaming] = useState(false);
    const [error, setError] = useState("");
    const [pendingApprovals, setPendingApprovals] = useState<ApprovalCardData[]>([]);
    const [decidingId, setDecidingId] = useState<string | null>(null);
    const [focusedMessageId, setFocusedMessageId] = useState<string | null>(null);
    const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
    const [inspectorOpen, setInspectorOpen] = useState(false);
    const [inspectorTab, setInspectorTab] = useState<"sources" | "trace">("sources");
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [user, setUser] = useState<User | null>(null);
    const [draft, setDraft] = useState("");
    const [attachment, setAttachment] = useState<UploadedFile | null>(null);
    const [attaching, setAttaching] = useState(false);
    const [resumeTargetId, setResumeTargetId] = useState<string | null>(null);

    const scrollRef = useRef<HTMLDivElement>(null);
    const abortRef = useRef<AbortController | null>(null);
    const stickRef = useRef(true);
    // 新建会话后跳过「按 activeId 拉历史」的那一次，否则会清掉乐观插入的消息。
    const skipLoadRef = useRef<string | null>(null);

    // ============ 登录态 ============
    useEffect(() => {
        if (!getToken()) {
            router.replace("/login");
            return;
        }
        getMe()
            .then((row) => {
                setUser(row);
            })
            .catch(() => undefined);
    }, [router]);

    useEffect(() => {
        return () => abortRef.current?.abort();
    }, []);

    // ============ 会话列表 ============
    const refreshThreads = useCallback(async () => {
        const rows = await listThreads();
        setThreads(rows);
        return rows;
    }, []);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const rows = await listThreads();
                if (cancelled) return;
                setThreads(rows);
                const wanted = new URLSearchParams(window.location.search).get("thread");
                const initial = wanted && rows.some((row) => row.id === wanted) ? wanted : rows[0]?.id ?? null;
                if (initial) setActiveId(initial);
            } catch (err) {
                if (!cancelled) setError(err instanceof Error ? err.message : "加载会话失败");
            } finally {
                if (!cancelled) setThreadsLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    // ============ 审批卡 ============
    const loadPending = useCallback(async (threadId: string): Promise<ApprovalCardData[]> => {
        try {
            const rows = await listApprovals("pending");
            return rows
                .filter((row) => row.thread_id === threadId)
                .map((row) => ({
                    approval_id: row.id,
                    tool_name: row.tool_name,
                    args: row.args_json,
                    risk_note: row.risk_note,
                    expires_at: row.expires_at,
                }));
        } catch {
            // 审批列表失败不该拦住历史消息。
            return [];
        }
    }, []);

    // ============ 切会话：拉历史 + 待审批 ============
    useEffect(() => {
        if (!activeId) return;
        if (skipLoadRef.current === activeId) {
            // 新建会话后，乐观插入的消息已经在屏幕上了，不能再拉一次空历史覆盖它。
            skipLoadRef.current = null;
            return;
        }

        let cancelled = false;
        stickRef.current = true;

        (async () => {
            setMessagesLoading(true);
            setError("");
            setFocusedMessageId(null);
            setActiveSourceId(null);

            try {
                const [data, cards] = await Promise.all([listMessages(activeId), loadPending(activeId)]);
                if (cancelled) return;

                setPendingApprovals(cards);

                if (cards.length > 0) {
                    // 中断轮次后端不落 assistant 消息，这里补一个占位气泡承接续流。
                    const lastUser = [...data.items].reverse().find((item) => item.role === "user");
                    const placeholder: ChatMessageType = {
                        id: tempId(),
                        role: "assistant",
                        content: "",
                        created_at: new Date().toISOString(),
                        waiting: true,
                        run_id: lastUser?.run_id ?? null,
                        startedAt: Date.now(),
                    };
                    setMessages([...data.items, placeholder]);
                    setResumeTargetId(placeholder.id);
                } else {
                    setMessages(data.items);
                    setResumeTargetId(null);
                }
            } catch (err) {
                if (!cancelled) setError(err instanceof Error ? err.message : "加载历史失败");
            } finally {
                if (!cancelled) setMessagesLoading(false);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [activeId, loadPending]);

    // ============ 滚动跟随 ============
    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        if (stickRef.current) el.scrollTop = el.scrollHeight;
    }, [messages]);

    useEffect(() => {
        if (pendingApprovals.length === 0) return;
        stickRef.current = true;
        const el = scrollRef.current;
        if (el) el.scrollTop = el.scrollHeight;
    }, [pendingApprovals.length]);

    // ============ 消费一条 SSE 流 ============
    const consume = useCallback(
        async (generator: AsyncGenerator<StreamEvent>, assistantId: string) => {
            try {
                for await (const evt of generator) {
                    if (evt.event === "message") {
                        const delta = evt.data.delta;
                        setMessages((prev) =>
                            prev.map((item) =>
                                item.id === assistantId
                                    ? { ...item, content: item.content + delta, streaming: true, waiting: false }
                                    : item
                            )
                        );
                    } else if (evt.event === "additional_info") {
                        const sources = evt.data.sources;
                        setMessages((prev) =>
                            prev.map((item) => (item.id === assistantId ? { ...item, sources } : item))
                        );
                        setFocusedMessageId(assistantId);
                    } else if (evt.event === "interrupt") {
                        const card = evt.data;
                        setPendingApprovals((prev) =>
                            prev.some((item) => item.approval_id === card.approval_id) ? prev : [...prev, card]
                        );
                        setResumeTargetId(assistantId);
                        setMessages((prev) =>
                            prev.map((item) =>
                                item.id === assistantId ? { ...item, waiting: true, streaming: false } : item
                            )
                        );
                    } else if (evt.event === "error") {
                        setError(evt.data.message);
                        setMessages((prev) =>
                            prev.map((item) => (item.id === assistantId ? { ...item, streaming: false } : item))
                        );
                    } else if (evt.event === "done") {
                        const interrupted = Boolean(evt.data.interrupted);
                        const runId = evt.data.run_id;
                        setMessages((prev) =>
                            prev.map((item) =>
                                item.id === assistantId
                                    ? {
                                          ...item,
                                          streaming: false,
                                          waiting: interrupted ? true : false,
                                          run_id: runId ?? item.run_id,
                                      }
                                    : item
                            )
                        );
                    }
                }
            } catch (err) {
                if (isAbortError(err)) {
                    setMessages((prev) =>
                        prev.map((item) =>
                            item.id === assistantId
                                ? {
                                      ...item,
                                      streaming: false,
                                      content: item.content || "（已停止生成）",
                                  }
                                : item
                        )
                    );
                } else {
                    setError(err instanceof Error ? err.message : "对话失败");
                    setMessages((prev) =>
                        prev.map((item) =>
                            item.id === assistantId
                                ? {
                                      ...item,
                                      streaming: false,
                                      content: item.content || "（生成失败，请稍后重试）",
                                  }
                                : item
                        )
                    );
                }
            } finally {
                setStreaming(false);
                abortRef.current = null;
                setMessages((prev) => prev.map((item) => (item.streaming ? { ...item, streaming: false } : item)));
                refreshThreads().catch(() => undefined);
            }
        },
        [refreshThreads]
    );

    // ============ 发送 ============
    const handleSend = useCallback(async () => {
        const text = draft.trim();
        if (!text || streaming || pendingApprovals.length > 0) return;

        setError("");
        setStreaming(true);

        let threadId = activeId;
        try {
            if (!threadId) {
                const thread = await createThread(text.slice(0, 24) || "新会话");
                threadId = thread.id;
                skipLoadRef.current = thread.id;
                setThreads((prev) => [thread, ...prev]);
                setActiveId(thread.id);
                setMessagesLoading(false);
                setInspectorTab("sources");
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "新建会话失败");
            setStreaming(false);
            return;
        }

        if (!threadId) {
            setStreaming(false);
            return;
        }

        // 点「新建会话」后直接发第一句：顺手用这句话当标题，别让侧栏一直挂着「新会话」。
        const currentThread = threads.find((row) => row.id === threadId);
        if (currentThread && currentThread.title === "新会话") {
            renameThread(threadId, text.slice(0, 24))
                .then((updated) => {
                    setThreads((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
                })
                .catch(() => undefined);
        }

        const assistantId = tempId();
        const now = new Date().toISOString();
        setMessages((prev) => [
            ...prev,
            { id: tempId(), role: "user", content: text, created_at: now },
            { id: assistantId, role: "assistant", content: "", created_at: now, streaming: true, startedAt: Date.now() },
        ]);
        setResumeTargetId(assistantId);
        setDraft("");
        setActiveSourceId(null);
        setFocusedMessageId(null);
        stickRef.current = true;

        const fileId = attachment?.file_id ?? null;
        setAttachment(null);

        const controller = new AbortController();
        abortRef.current = controller;

        try {
            const stream = await streamChat(threadId, text, fileId, controller.signal);
            await consume(stream, assistantId);
        } catch (err) {
            if (!isAbortError(err)) {
                setError(err instanceof Error ? err.message : "发送失败");
                setMessages((prev) =>
                    prev.map((item) =>
                        item.id === assistantId
                            ? { ...item, streaming: false, content: item.content || "（发送失败，请重试）" }
                            : item
                    )
                );
            }
            setStreaming(false);
            abortRef.current = null;
        }
    }, [activeId, attachment, consume, draft, pendingApprovals.length, streaming, threads]);

    // ============ 审批决策 ============
    const handleDecide = useCallback(
        async (card: ApprovalCardData, decision: "approve" | "reject", note?: string) => {
            if (decidingId) return;

            setDecidingId(card.approval_id);
            setPendingApprovals((prev) => prev.filter((item) => item.approval_id !== card.approval_id));
            setStreaming(true);
            setError("");
            stickRef.current = true;

            const controller = new AbortController();
            abortRef.current = controller;

            try {
                const stream = await decideApproval(card.approval_id, decision, note, controller.signal);
                // 审批动作发生在「续流回答」之前，所以这枚系统消息要插在目标气泡上面。
                const chip = systemMessage(
                    `${decision === "approve" ? "已批准" : "已拒绝"}「${toolLabel(card.tool_name)}」`
                );
                let targetId = resumeTargetId;
                if (!targetId) {
                    targetId = tempId();
                    const now = new Date().toISOString();
                    setMessages((prev) => [
                        ...prev,
                        chip,
                        {
                            id: targetId as string,
                            role: "assistant",
                            content: "",
                            created_at: now,
                            streaming: true,
                            startedAt: Date.now(),
                        },
                    ]);
                    setResumeTargetId(targetId);
                } else {
                    setMessages((prev) => {
                        const index = prev.findIndex((item) => item.id === targetId);
                        const updated = prev.map((item) =>
                            item.id === targetId ? { ...item, streaming: true, waiting: false } : item
                        );
                        if (index === -1) return [...updated, chip];
                        return [...updated.slice(0, index), chip, ...updated.slice(index)];
                    });
                }
                await consume(stream, targetId);
            } catch (err) {
                if (!isAbortError(err)) {
                    setError(err instanceof Error ? err.message : "审批失败，请刷新重试");
                }
                setStreaming(false);
                abortRef.current = null;
                if (activeId) {
                    const cards = await loadPending(activeId);
                    setPendingApprovals(cards);
                }
            } finally {
                setDecidingId(null);
            }
        },
        [activeId, consume, decidingId, loadPending, resumeTargetId]
    );

    // ============ 会话操作 ============
    const handleSelectThread = useCallback(
        (id: string) => {
            setSidebarOpen(false);
            setInspectorOpen(false);
            if (id === activeId) return;
            if (streaming) abortRef.current?.abort();
            setActiveId(id);
            setMessages([]);
            setMessagesLoading(true);
            setPendingApprovals([]);
            setDraft("");
            setAttachment(null);
            setInspectorTab("sources");
            stickRef.current = true;
        },
        [activeId, streaming]
    );

    const handleCreateThread = useCallback(async () => {
        if (streaming) abortRef.current?.abort();
        try {
            const thread = await createThread();
            setThreads((prev) => [thread, ...prev]);
            setActiveId(thread.id);
            setMessages([]);
            setMessagesLoading(false);
            setPendingApprovals([]);
            setDraft("");
            setInspectorTab("sources");
            setSidebarOpen(false);
        } catch (err) {
            setError(err instanceof Error ? err.message : "新建会话失败");
        }
    }, [streaming]);

    const handleDeleteThread = useCallback(
        async (id: string) => {
            try {
                if (id === activeId) abortRef.current?.abort();
                await deleteThread(id);
                const rows = await refreshThreads();
                if (id === activeId) {
                    setActiveId(rows[0]?.id ?? null);
                    setMessages([]);
                    setMessagesLoading(Boolean(rows[0]));
                    setPendingApprovals([]);
                    setInspectorTab("sources");
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : "删除失败");
            }
        },
        [activeId, refreshThreads]
    );

    const handleRenameThread = useCallback(async (id: string, title: string) => {
        try {
            const updated = await renameThread(id, title);
            setThreads((prev) => prev.map((thread) => (thread.id === id ? updated : thread)));
        } catch (err) {
            setError(err instanceof Error ? err.message : "重命名失败");
        }
    }, []);

    const handleLogout = useCallback(() => {
        abortRef.current?.abort();
        clearToken();
        router.replace("/login");
    }, [router]);

    const handleAttach = useCallback(async (file: File) => {
        if (file.size > 20 * 1024 * 1024) {
            setError("文件超过 20MB，请分段提问或先加入知识库");
            return;
        }
        setAttaching(true);
        setError("");
        try {
            const uploaded = await uploadFile(file);
            setAttachment(uploaded);
        } catch (err) {
            setError(err instanceof Error ? err.message : "附件上传失败");
        } finally {
            setAttaching(false);
        }
    }, []);

    const handleStop = useCallback(() => {
        abortRef.current?.abort();
    }, []);

    // ============ 派生数据 ============
    const activeThread = threads.find((thread) => thread.id === activeId) ?? null;

    const panel = useMemo(() => {
        const assistantMessages = messages.filter((item) => item.role === "assistant");
        const focused = focusedMessageId ? messages.find((item) => item.id === focusedMessageId) : undefined;
        const withSources = [...assistantMessages].reverse().find((item) => normalizeSources(item.sources).length > 0);
        const sourceMessage =
            focused && normalizeSources(focused.sources).length > 0 ? focused : withSources ?? assistantMessages.at(-1);
        const runMessage = focused?.run_id ? focused : [...assistantMessages].reverse().find((item) => item.run_id);
        return {
            sources: normalizeSources(sourceMessage?.sources) as Source[],
            runId: runMessage?.run_id ?? null,
        };
    }, [focusedMessageId, messages]);

    const status = streaming
        ? { label: "生成中", dot: "bg-running", text: "text-running" }
        : pendingApprovals.length > 0
          ? { label: `待审批 ${pendingApprovals.length}`, dot: "bg-waiting", text: "text-waiting-foreground" }
          : { label: "就绪", dot: "bg-success", text: "text-muted-foreground" };

    const visibleCount = messages.filter((item) => item.role === "user" || item.role === "assistant").length;

    return (
        <div className="flex h-[100dvh] w-full overflow-hidden bg-background">
            <Sidebar
                threads={threads}
                activeId={activeId}
                loading={threadsLoading}
                user={user}
                open={sidebarOpen}
                streaming={streaming}
                onClose={() => setSidebarOpen(false)}
                onSelect={handleSelectThread}
                onCreate={handleCreateThread}
                onDelete={handleDeleteThread}
                onRename={handleRenameThread}
                onLogout={handleLogout}
            />

            <main className="flex min-w-0 flex-1 flex-col">
                <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur-md sm:px-5">
                    <button
                        type="button"
                        onClick={() => setSidebarOpen(true)}
                        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
                        aria-label="打开侧栏"
                    >
                        <Menu className="size-4" />
                    </button>

                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                            <h1 className="truncate text-sm font-medium tracking-tight">
                                {activeThread?.title ?? "新会话"}
                            </h1>
                            <span
                                className={cn(
                                    "inline-flex shrink-0 items-center gap-1.5 rounded-full border bg-card px-2 py-0.5 text-[10px]",
                                    status.text
                                )}
                            >
                                <span className={cn("size-1.5 rounded-full", status.dot, streaming && "animate-pulse")} />
                                {status.label}
                            </span>
                        </div>
                        <p className="truncate text-[10px] text-muted-foreground">
                            {activeThread
                                ? `${visibleCount} 条消息 · 更新于 ${formatRelative(activeThread.updated_at)}`
                                : "直接输入问题，会自动开一个新会话"}
                        </p>
                    </div>

                    <Link
                        href="/knowledge"
                        className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground sm:inline-flex"
                    >
                        <BookOpen className="size-3.5" />
                        知识库
                    </Link>

                    <ThemeToggle className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden" />

                    <button
                        type="button"
                        onClick={() => setInspectorOpen(true)}
                        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground xl:hidden"
                        aria-label="打开引用与轨迹"
                    >
                        <PanelRight className="size-4" />
                    </button>
                </header>

                <div
                    ref={scrollRef}
                    onScroll={(event) => {
                        const el = event.currentTarget;
                        stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
                    }}
                    className="scroll-slim relative min-h-0 flex-1 overflow-y-auto"
                >
                    <div className="mx-auto w-full max-w-3xl space-y-5 px-3 py-6 sm:px-5">
                        {messagesLoading && (
                            <div className="space-y-4">
                                {[0, 1, 2].map((index) => (
                                    <div key={index} className="skeleton h-20 rounded-2xl" />
                                ))}
                            </div>
                        )}

                        {!messagesLoading && messages.length === 0 && pendingApprovals.length === 0 && (
                            <div className="fade-up relative overflow-hidden rounded-2xl border bg-card px-5 py-10 text-center sm:px-8">
                                <div className="dot-grid pointer-events-none absolute inset-0 opacity-40" aria-hidden />
                                <div className="relative">
                                    <BrandMark className="mx-auto size-10" />
                                    <h2 className="mt-4 text-lg font-semibold tracking-tight">
                                        让每一句话都有出处
                                    </h2>
                                    <p className="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-muted-foreground">
                                        问它文档里的事实，它会先检索、再回答，并把引用的原文放在右栏；
                                        要写文件时会停下来，等你点头。
                                    </p>

                                    <div className="mx-auto mt-5 grid max-w-xl gap-2 sm:grid-cols-3">
                                        {SUGGESTIONS.map((item) => (
                                            <button
                                                key={item.title}
                                                type="button"
                                                onClick={() => setDraft(item.prompt)}
                                                className="rounded-xl border bg-card p-3 text-left transition-colors hover:bg-accent/60"
                                            >
                                                <p className="flex items-center gap-1.5 text-xs font-medium">
                                                    <Sparkles className="size-3 text-muted-foreground" />
                                                    {item.title}
                                                </p>
                                                <p className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-muted-foreground">
                                                    {item.prompt}
                                                </p>
                                            </button>
                                        ))}
                                    </div>

                                    {!activeId && (
                                        <p className="mt-4 text-[10px] text-muted-foreground">
                                            还没有会话也没关系，直接输入就会自动创建。
                                        </p>
                                    )}
                                </div>
                            </div>
                        )}

                        {messages.map((message) => (
                            <ChatMessage
                                key={message.id}
                                message={message}
                                activeSourceId={activeSourceId}
                                onCite={(sourceId) => {
                                    setFocusedMessageId(message.id);
                                    setActiveSourceId(sourceId);
                                    setInspectorTab("sources");
                                    setInspectorOpen(true);
                                }}
                                onOpenSources={(target) => {
                                    setFocusedMessageId(target.id);
                                    setActiveSourceId(null);
                                    setInspectorTab("sources");
                                    setInspectorOpen(true);
                                }}
                                onOpenTrace={(runId) => router.push(`/traces/${runId}`)}
                            />
                        ))}

                        {pendingApprovals.map((card) => (
                            <ApprovalCard
                                key={card.approval_id}
                                card={card}
                                busy={decidingId === card.approval_id}
                                onDecide={(decision, note) => void handleDecide(card, decision, note)}
                            />
                        ))}

                        <div className="h-1" />
                    </div>
                </div>

                {error && (
                    <div className="mx-3 mb-2 flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/5 px-3 py-2 text-xs text-destructive sm:mx-5">
                        <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
                        <span className="flex-1 leading-relaxed">{error}</span>
                        <button
                            type="button"
                            onClick={() => setError("")}
                            className="rounded p-0.5 transition-colors hover:bg-destructive/10"
                            aria-label="关闭提示"
                        >
                            <X className="size-3.5" />
                        </button>
                    </div>
                )}

                <Composer
                    value={draft}
                    onChange={setDraft}
                    onSend={() => void handleSend()}
                    streaming={streaming}
                    disabled={pendingApprovals.length > 0}
                    attachment={attachment}
                    attaching={attaching}
                    onAttach={(file) => void handleAttach(file)}
                    onRemoveAttachment={() => setAttachment(null)}
                    onStop={handleStop}
                    placeholder={
                        pendingApprovals.length > 0
                            ? "先处理上面的审批卡，再继续提问…"
                            : activeId
                              ? "问点什么，或把文档里的问题丢进来…"
                              : "直接输入问题，会自动创建会话…"
                    }
                />
            </main>

            <Inspector
                open={inspectorOpen}
                onClose={() => setInspectorOpen(false)}
                tab={inspectorTab}
                onTabChange={setInspectorTab}
                sources={panel.sources}
                activeSourceId={activeSourceId}
                onSelectSource={setActiveSourceId}
                runId={panel.runId}
            />
        </div>
    );
}
