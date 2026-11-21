import type { Metadata, Viewport } from "next";
// 用 geist 包自托管字体：构建时不访问 Google Fonts，国内服务器也能构建。
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata: Metadata = {
    title: "Steward · AI 工作台",
    description: "可控、可回放的 AI 助手：文档检索、引用溯源、危险操作审批、全链路轨迹。",
};

export const viewport: Viewport = {
    themeColor: [
        { media: "(prefers-color-scheme: light)", color: "#fafafa" },
        { media: "(prefers-color-scheme: dark)", color: "#121212" },
    ],
};

// 在首帧之前定好主题，避免刷新时白闪一下。
const THEME_SCRIPT = `(function(){try{var v=localStorage.getItem("steward_theme")||"system";var d=v==="dark"||(v==="system"&&window.matchMedia("(prefers-color-scheme: dark)").matches);var r=document.documentElement;r.classList.toggle("dark",d);r.style.colorScheme=d?"dark":"light";}catch(e){}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
    return (
        <html lang="zh-CN" suppressHydrationWarning>
            <head>
                <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
            </head>
            <body className={`${GeistSans.variable} ${GeistMono.variable} antialiased`}>
                {children}
            </body>
        </html>
    );
}
