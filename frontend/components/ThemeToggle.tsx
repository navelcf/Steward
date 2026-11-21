"use client";

import { Moon, Sun } from "lucide-react";

const THEME_KEY = "steward_theme";

// 亮暗两个图标都渲染，用 CSS 的 dark: 变体决定显示哪一个。
// 这样不需要在 effect 里读 DOM 再 setState，也不会出现首帧图标闪一下。
export default function ThemeToggle({ className }: { className?: string }) {
    function toggle() {
        const root = document.documentElement;
        const next = !root.classList.contains("dark");
        root.classList.toggle("dark", next);
        root.style.colorScheme = next ? "dark" : "light";
        window.localStorage.setItem(THEME_KEY, next ? "dark" : "light");
    }

    return (
        <button
            type="button"
            onClick={toggle}
            title="切换亮色 / 暗色"
            aria-label="切换亮色 / 暗色"
            className={
                className ??
                "flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            }
        >
            <Moon className="size-4 dark:hidden" />
            <Sun className="hidden size-4 dark:block" />
        </button>
    );
}
