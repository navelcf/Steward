// 工具中文名只在展示层用，后端仍然认 name。
export const TOOL_LABELS: Record<string, string> = {
    save_note: "保存笔记",
    search_docs: "文档检索",
    get_current_time: "当前时间",
};

export function toolLabel(name: string): string {
    return TOOL_LABELS[name] ?? name;
}
