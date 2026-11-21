"use client";

import { useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";
import type { Source } from "@/lib/types";
import { cn } from "@/lib/cn";

type Props = {
    content: string;
    sources?: Source[] | null;
    activeSourceId?: string | null;
    onCite?: (sourceId: string) => void;
};

// 把正文里的 [ref-xxxxxxxx] 换成 markdown 链接，交给下面的 a 渲染器变成小芯片。
// 代码块（```...``` 和 `...`）里不动，避免把示例代码改坏。
function linkifyCitations(content: string, sources: Source[]): string {
    if (sources.length === 0) return content;

    const indexById = new Map(sources.map((source, index) => [source.source_id, index + 1]));
    const parts = content.split(/(```[\s\S]*?```|`[^`\n]*`)/g);

    return parts
        .map((part, index) => {
            if (index % 2 === 1) return part;
            return part.replace(/\[(ref-[A-Za-z0-9_-]+)\]/g, (match, id: string) => {
                const number = indexById.get(id);
                return number ? `[${number}](#cite-${id})` : match;
            });
        })
        .join("");
}

// 代码块右上角的复制按钮；放在 wrapper 里，hover 才显形。
function CodeBlock({ children }: { children: React.ReactNode }) {
    const ref = useRef<HTMLPreElement>(null);
    const [copied, setCopied] = useState(false);

    async function copy() {
        const text = ref.current?.innerText ?? "";
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1600);
        } catch {
            // 剪贴板权限被拒时静默失败，不打断阅读。
        }
    }

    return (
        <div className="group/code relative my-2">
            <button
                type="button"
                onClick={copy}
                title="复制代码"
                className="absolute right-2 top-2 z-10 flex items-center gap-1 rounded-md border bg-card/90 px-1.5 py-1 text-[11px] text-muted-foreground opacity-0 shadow-sm backdrop-blur transition-opacity hover:text-foreground group-hover/code:opacity-100"
            >
                {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
                {copied ? "已复制" : "复制"}
            </button>
            <pre ref={ref}>{children}</pre>
        </div>
    );
}

export default function Markdown({ content, sources, activeSourceId, onCite }: Props) {
    const list = sources ?? [];
    const text = linkifyCitations(content, list);

    const components: Components = {
        a: ({ href, children }) => {
            if (href?.startsWith("#cite-")) {
                const id = href.slice("#cite-".length);
                return (
                    <button
                        type="button"
                        data-active={activeSourceId === id}
                        onClick={() => onCite?.(id)}
                        title="查看引用来源"
                        className="cite-chip"
                    >
                        {children}
                    </button>
                );
            }
            return (
                <a href={href} target="_blank" rel="noreferrer noopener">
                    {children}
                </a>
            );
        },
        pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
        table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
                <table>{children}</table>
            </div>
        ),
    };

    return (
        <div className={cn("md-body")}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {text || " "}
            </ReactMarkdown>
        </div>
    );
}
