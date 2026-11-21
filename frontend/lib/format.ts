// 展示层的格式化函数；只处理「看起来舒服」，不改数据。

export function formatClock(iso: string): string {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export function formatDateTime(iso: string): string {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });
}

export function formatRelative(iso: string): string {
    const time = new Date(iso).getTime();
    if (Number.isNaN(time)) return "";

    const diff = Date.now() - time;
    const minute = 60_000;
    const hour = 60 * minute;
    const day = 24 * hour;

    if (diff < minute) return "刚刚";
    if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`;
    if (diff < day) return `${Math.floor(diff / hour)} 小时前`;
    if (diff < 2 * day) return "昨天";
    if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`;
    return formatDateTime(iso);
}

export function formatBytes(bytes: number): string {
    if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / 1024 ** index;
    return `${value >= 10 || index === 0 ? Math.round(value) : value.toFixed(1)} ${units[index]}`;
}

export function formatNumber(value: number | null | undefined): string {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatDuration(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return "—";
    if (ms < 1000) return `${Math.round(ms)} ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
    return `${Math.floor(ms / 60_000)} 分 ${Math.round((ms % 60_000) / 1000)} 秒`;
}

export function formatElapsed(startedAt: number): string {
    const seconds = Math.max(0, (Date.now() - startedAt) / 1000);
    return seconds < 10 ? `${seconds.toFixed(1)}s` : `${Math.round(seconds)}s`;
}

// 审批卡倒计时；后端 expires_at 是 ISO 字符串。
export function formatExpiry(expiresAt: string | null): string {
    if (!expiresAt) return "长期有效";
    const diff = new Date(expiresAt).getTime() - Date.now();
    if (Number.isNaN(diff)) return "";
    if (diff <= 0) return "已过期";

    const minute = 60_000;
    if (diff < minute) return `剩 ${Math.ceil(diff / 1000)} 秒`;
    const minutes = Math.floor(diff / minute);
    if (minutes < 60) return `剩 ${minutes} 分钟`;
    return `剩 ${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`;
}

export function isExpired(expiresAt: string | null): boolean {
    if (!expiresAt) return false;
    const time = new Date(expiresAt).getTime();
    return !Number.isNaN(time) && time <= Date.now();
}

export function suffixOf(filename: string): string {
    const index = filename.lastIndexOf(".");
    return index >= 0 ? filename.slice(index + 1).toLowerCase() : "";
}
