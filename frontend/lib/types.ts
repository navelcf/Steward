// 后端 Pydantic 模型的镜像。字段名改后端时，这里必须同步改。

export type User = {
    id: number;
    email: string;
    display_name: string | null;
};

export type Thread = {
    id: string;
    title: string;
    active_workflow: string | null;
    created_at: string;
    updated_at: string;
};

export type MessageRole = "user" | "assistant" | "tool" | "system";

// 检索引用；字段来自 retrieve_sources() 的返回。
export type Source = {
    source_id: string;
    doc_id: string;
    clause_name: string;
    section_path: string;
    content: string;
};

// 一条消息：后端历史（数字 id）和本地乐观插入（tmp- 开头）共用这个形状。
export type ChatMessage = {
    id: string;
    role: MessageRole;
    content: string;
    created_at: string;
    sources?: Source[] | null;
    run_id?: string | null;
    // 还在接收 delta。
    streaming?: boolean;
    // 停在审批中断点，等用户点按钮。
    waiting?: boolean;
    // 本轮开始时间戳，用来显示「已思考 2.4s」。
    startedAt?: number;
};

export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";

export type ApprovalCardData = {
    approval_id: string;
    tool_name: string;
    args: Record<string, unknown>;
    risk_note: string | null;
    expires_at: string | null;
};

export type ApprovalRecord = {
    id: string;
    thread_id: string;
    tool_name: string;
    args_json: Record<string, unknown>;
    edited_args: Record<string, unknown> | null;
    risk_note: string | null;
    status: ApprovalStatus;
    decided_at: string | null;
    decision_note: string | null;
    expires_at: string | null;
    created_at: string;
};

export type DonePayload = {
    ok: boolean;
    run_id?: string;
    message_id?: number;
    sources?: number;
    interrupted?: boolean;
    cards?: number;
};

export type StreamEvent =
    | { event: "message"; data: { delta: string } }
    | { event: "additional_info"; data: { sources: Source[] } }
    | { event: "interrupt"; data: ApprovalCardData }
    | { event: "error"; data: { message: string } }
    | { event: "done"; data: DonePayload };

export type TraceStep = {
    step: number;
    kind: string;
    name: string | null;
    input: Record<string, unknown> | null;
    output: Record<string, unknown> | null;
    latency_ms: number | null;
    prompt_tokens: number | null;
    completion_tokens: number | null;
    created_at: string;
};

export type Trace = {
    run_id: string;
    thread_id: string;
    steps: TraceStep[];
};

export type DocumentRow = {
    id: string;
    filename: string;
    mime_type: string;
    size_bytes: number;
    status: string;
    version: number;
    page_count: number | null;
    char_count: number | null;
    is_indexed: boolean;
    parser: string | null;
    error_message: string | null;
    created_at: string;
};

export type SearchHit = {
    child_id: string;
    doc_id: string;
    parent_id: string;
    section_path: string;
    raw_content: string;
    score: number;
};

export type SearchResult = {
    query: string;
    hits: SearchHit[];
};

export type UploadedFile = {
    file_id: string;
    filename: string;
    suffix: string;
    size: number;
    char_count: number;
    token_estimate: number;
};
