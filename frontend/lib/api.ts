import type {
    ApprovalRecord,
    ChatMessage,
    DocumentRow,
    SearchResult,
    Source,
    StreamEvent,
    Thread,
    Trace,
    TraceStep,
    UploadedFile,
    User,
} from "./types";

// 后端地址走环境变量；末尾斜杠统一去掉，避免拼出 //api。
// 没配时：dev 回落到本机 8001；生产回落到空串，走同源（通常由 nginx 把 /api 反代到后端）。
const FALLBACK_BASE = process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:8001";
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? FALLBACK_BASE).replace(/\/+$/, "");

const TOKEN_KEY = "steward_token";

// ============ 登录态 ============

export function getToken(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
    window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(TOKEN_KEY);
}

// 401 统一处理：清 token、回登录页。已经在登录页就不要反复跳。
function handleUnauthorized(): void {
    clearToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        // 这里是 fetch 层，拿不到 next/navigation 的 router，只能整页跳。
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = "/login";
    }
}

// FastAPI 的错误体：detail 可能是字符串，也可能是 422 的数组。
async function readError(response: Response): Promise<string> {
    const fallback = `请求失败（${response.status}）`;
    try {
        const text = await response.text();
        if (!text) return fallback;
        const body = JSON.parse(text) as { detail?: unknown };
        const detail = body.detail;
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail)) {
            const parts = detail
                .map((item) => {
                    if (item && typeof item === "object" && "msg" in item) {
                        const msg = (item as { msg?: unknown }).msg;
                        return typeof msg === "string" ? msg : "";
                    }
                    return "";
                })
                .filter(Boolean);
            if (parts.length > 0) return parts.join("；");
        }
        return fallback;
    } catch {
        return fallback;
    }
}

// 统一 JSON 请求：自动带 token，401 踢回登录，204 返回 undefined。
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body && !(init.body instanceof FormData)) {
        headers.set("Content-Type", "application/json");
    }
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${API_BASE}${path}`, { ...init, headers });

    if (response.status === 401) {
        handleUnauthorized();
        throw new Error("登录已过期，请重新登录");
    }
    if (!response.ok) {
        throw new Error(await readError(response));
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
}

// ============ 认证 ============

export async function login(email: string, password: string): Promise<string> {
    const data = await request<{ access_token: string }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
    });
    return data.access_token;
}

export async function register(email: string, password: string, displayName?: string): Promise<User> {
    return request<User>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({
            email,
            password,
            display_name: displayName?.trim() || null,
        }),
    });
}

export function getMe(): Promise<User> {
    return request<User>("/api/v1/auth/me");
}

// ============ 会话 ============

export function listThreads(limit = 50): Promise<Thread[]> {
    return request<Thread[]>(`/api/v1/threads?limit=${limit}`);
}

export function createThread(title = "新会话"): Promise<Thread> {
    return request<Thread>("/api/v1/threads", {
        method: "POST",
        body: JSON.stringify({ title }),
    });
}

export function renameThread(id: string, title: string): Promise<Thread> {
    return request<Thread>(`/api/v1/threads/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
    });
}

export function deleteThread(id: string): Promise<void> {
    return request<void>(`/api/v1/threads/${id}`, { method: "DELETE" });
}

export function clearMessages(threadId: string): Promise<void> {
    return request<void>(`/api/v1/threads/${threadId}/messages`, { method: "DELETE" });
}

// ============ 历史消息 ============

type MessageListResponse = {
    items: Array<{
        id: number;
        thread_id: string;
        role: string;
        content: string;
        sources: Source[] | null;
        run_id: string | null;
        created_at: string;
    }>;
    total: number;
};

export async function listMessages(threadId: string, limit = 200): Promise<{ items: ChatMessage[]; total: number }> {
    const data = await request<MessageListResponse>(`/api/v1/threads/${threadId}/messages?limit=${limit}`);
    return {
        total: data.total,
        items: data.items.map((row) => ({
            id: String(row.id),
            role: row.role === "user" || row.role === "assistant" || row.role === "tool" ? row.role : "assistant",
            content: row.content,
            created_at: row.created_at,
            sources: row.sources,
            run_id: row.run_id,
        })),
    };
}

// ============ SSE 解析 ============
// SSE 事件以空行分隔；TCP 会把流切碎，所以必须自己维护 buffer。
export async function* parseSSE(response: Response): AsyncGenerator<StreamEvent> {
    if (!response.body) throw new Error("响应没有 body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            let separator = buffer.match(/\r?\n\r?\n/);
            while (separator && separator.index !== undefined) {
                const raw = buffer.slice(0, separator.index);
                buffer = buffer.slice(separator.index + separator[0].length);
                const event = parseEvent(raw);
                if (event) yield event;
                separator = buffer.match(/\r?\n\r?\n/);
            }
        }

        // 流结束时可能有最后一帧没有空行结尾。
        const tail = buffer.trim();
        if (tail) {
            const event = parseEvent(tail);
            if (event) yield event;
        }
    } finally {
        reader.releaseLock();
    }
}

function parseEvent(raw: string): StreamEvent | null {
    let name = "message";
    const dataLines: string[] = [];

    for (const line of raw.split(/\r?\n/)) {
        if (line.startsWith(":")) continue;
        if (line.startsWith("event:")) {
            name = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
            // 标准是 "data: "，只去掉一个空格；trim() 会吃掉正文开头的空白。
            dataLines.push(line.slice(5).replace(/^ /, ""));
        }
    }

    if (dataLines.length === 0) return null;
    try {
        const payload = JSON.parse(dataLines.join("\n")) as unknown;
        return { event: name, data: payload } as StreamEvent;
    } catch {
        console.warn("SSE 事件不是合法 JSON，已跳过", name, dataLines.join("\n").slice(0, 200));
        return null;
    }
}

// 开一条 POST 流；404/409 这类错误在响应头之前，会走这里抛出来。
async function openStream(path: string, body: unknown, signal?: AbortSignal): Promise<AsyncGenerator<StreamEvent>> {
    const token = getToken();
    const response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal,
    });

    if (response.status === 401) {
        handleUnauthorized();
        throw new Error("登录已过期，请重新登录");
    }
    if (!response.ok) {
        throw new Error(await readError(response));
    }
    return parseSSE(response);
}

export function streamChat(
    threadId: string,
    message: string,
    fileId?: string | null,
    signal?: AbortSignal
): Promise<AsyncGenerator<StreamEvent>> {
    return openStream(
        "/api/v1/chat/stream",
        { thread_id: threadId, message, file_id: fileId ?? null },
        signal
    );
}

export function decideApproval(
    approvalId: string,
    decision: "approve" | "reject",
    note?: string,
    signal?: AbortSignal
): Promise<AsyncGenerator<StreamEvent>> {
    return openStream(
        `/api/v1/approvals/${approvalId}/decide`,
        { decision, note: note?.trim() || null },
        signal
    );
}

// ============ 审批 ============

export function listApprovals(status?: string, limit = 100): Promise<ApprovalRecord[]> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (status) query.set("status", status);
    return request<ApprovalRecord[]>(`/api/v1/approvals?${query.toString()}`);
}

// ============ 轨迹 ============

export function listTraces(threadId: string, limit = 300): Promise<TraceStep[]> {
    return request<TraceStep[]>(`/api/v1/traces?thread_id=${threadId}&limit=${limit}`);
}

export function getTrace(runId: string): Promise<Trace> {
    return request<Trace>(`/api/v1/traces/${runId}`);
}

// ============ 文件 / 知识库 ============

export async function uploadFile(file: File, signal?: AbortSignal): Promise<UploadedFile> {
    const form = new FormData();
    form.append("file", file);
    return request<UploadedFile>("/api/v1/files", { method: "POST", body: form, signal });
}

export async function uploadDocument(file: File, signal?: AbortSignal): Promise<DocumentRow> {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentRow>("/api/v1/documents", { method: "POST", body: form, signal });
}

export function listDocuments(limit = 100): Promise<DocumentRow[]> {
    return request<DocumentRow[]>(`/api/v1/documents?limit=${limit}`);
}

export function deleteDocument(id: string): Promise<void> {
    return request<void>(`/api/v1/documents/${id}`, { method: "DELETE" });
}

export function searchKnowledge(query: string, topK = 20): Promise<SearchResult> {
    return request<SearchResult>("/api/v1/search", {
        method: "POST",
        body: JSON.stringify({ query, top_k: topK }),
    });
}

// ============ 小工具 ============

export function tempId(): string {
    return `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function normalizeSources(sources: Source[] | null | undefined): Source[] {
    return Array.isArray(sources) ? sources : [];
}

export function firstLine(text: string, max = 90): string {
    const line = text.replace(/\s+/g, " ").trim();
    return line.length > max ? `${line.slice(0, max)}…` : line;
}
