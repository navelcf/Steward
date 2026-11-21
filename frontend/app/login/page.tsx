"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowRight,
    BookOpenCheck,
    Eye,
    EyeOff,
    GitBranch,
    Loader2,
    ShieldCheck,
} from "lucide-react";
import BrandMark from "@/components/BrandMark";
import ThemeToggle from "@/components/ThemeToggle";
import { getToken, login, register, setToken } from "@/lib/api";
import { cn } from "@/lib/cn";

type Mode = "login" | "register";

export default function LoginPage() {
    const router = useRouter();
    const [mode, setMode] = useState<Mode>("login");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirm, setConfirm] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    // 已登录直接进工作台。
    useEffect(() => {
        if (getToken()) router.replace("/");
    }, [router]);

    async function submit(event: React.FormEvent) {
        event.preventDefault();
        setError("");

        if (mode === "register") {
            if (password.length < 8) {
                setError("密码至少 8 位");
                return;
            }
            if (password !== confirm) {
                setError("两次输入的密码不一致");
                return;
            }
        }

        setBusy(true);
        try {
            if (mode === "register") {
                await register(email, password, displayName);
            }
            const token = await login(email, password);
            setToken(token);
            router.replace("/");
        } catch (err) {
            setError(err instanceof Error ? err.message : "操作失败，请稍后重试");
        } finally {
            setBusy(false);
        }
    }

    function switchMode(next: Mode) {
        setMode(next);
        setError("");
        setPassword("");
        setConfirm("");
    }

    return (
        <main className="grid min-h-[100dvh] lg:grid-cols-[1.05fr_1fr]">
            {/* 左：品牌墙。石墨底 + 点阵，不放渐变。 */}
            <section className="relative hidden flex-col justify-between overflow-hidden bg-brand p-12 text-brand-foreground lg:flex">
                <div className="dot-grid-light pointer-events-none absolute inset-0 opacity-70" aria-hidden />

                <div className="relative flex items-center gap-2.5 text-sm font-semibold tracking-tight">
                    <span className="flex size-8 items-center justify-center rounded-xl bg-brand-foreground text-brand">
                        <ShieldCheck className="size-4" strokeWidth={2.2} />
                    </span>
                    Steward
                </div>

                <div className="relative max-w-lg space-y-8">
                    <h1 className="text-[2.6rem] font-semibold leading-[1.14] tracking-tighter">
                        一个会
                        <span className="mx-1 underline decoration-2 underline-offset-[7px]">查资料</span>
                        、
                        <br />
                        也会
                        <span className="mx-1 underline decoration-2 underline-offset-[7px]">等你点头</span>
                        的助手
                    </h1>

                    <p className="max-w-md text-sm leading-relaxed text-brand-foreground/65">
                        RAG 检索、引用溯源、危险操作审批、全链路轨迹回放。
                        它不是一个只会说话的黑盒 —— 每一步都留痕，每一个判断都能追问。
                    </p>

                    <ul className="grid gap-3 text-[13px]">
                        <li className="flex items-start gap-3">
                            <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md border border-brand-foreground/20">
                                <BookOpenCheck className="size-3.5" />
                            </span>
                            <div>
                                <p className="font-medium">查得到</p>
                                <p className="text-brand-foreground/55">混合检索你的文档，回答里带 [1] 这样的引用编号。</p>
                            </div>
                        </li>
                        <li className="flex items-start gap-3">
                            <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md border border-brand-foreground/20">
                                <GitBranch className="size-3.5" />
                            </span>
                            <div>
                                <p className="font-medium">说得清</p>
                                <p className="text-brand-foreground/55">模型调用、工具参数、耗时与 token，逐步可回放。</p>
                            </div>
                        </li>
                        <li className="flex items-start gap-3">
                            <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md border border-brand-foreground/20">
                                <ShieldCheck className="size-3.5" />
                            </span>
                            <div>
                                <p className="font-medium">拦得住</p>
                                <p className="text-brand-foreground/55">写文件、动数据之前先停下来，等你批准再执行。</p>
                            </div>
                        </li>
                    </ul>
                </div>

                <div className="relative flex items-center gap-2 text-[11px] text-brand-foreground/40">
                    <span>LangGraph</span>
                    <span>·</span>
                    <span>Milvus</span>
                    <span>·</span>
                    <span>DeepSeek</span>
                    <span>·</span>
                    <span>FastAPI</span>
                </div>
            </section>

            {/* 右：表单 */}
            <section className="relative flex items-center justify-center px-6 py-12">
                <div className="absolute right-5 top-5">
                    <ThemeToggle />
                </div>

                <div className="w-full max-w-sm">
                    <div className="mb-8 flex items-center gap-2.5 lg:hidden">
                        <BrandMark className="size-8" />
                        <span className="text-sm font-semibold tracking-tight">Steward</span>
                    </div>

                    <div className="mb-7 space-y-1.5">
                        <h2 className="text-2xl font-semibold tracking-tight">
                            {mode === "login" ? "欢迎回来" : "创建账号"}
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            {mode === "login" ? "用邮箱登录，继续你的工作台。" : "注册后会直接登录，无需邮箱验证。"}
                        </p>
                    </div>

                    <div className="mb-6 flex rounded-full bg-muted p-1">
                        <button
                            type="button"
                            onClick={() => switchMode("login")}
                            className={cn(
                                "flex-1 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                                mode === "login" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"
                            )}
                        >
                            登录
                        </button>
                        <button
                            type="button"
                            onClick={() => switchMode("register")}
                            className={cn(
                                "flex-1 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                                mode === "register" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"
                            )}
                        >
                            注册
                        </button>
                    </div>

                    <form onSubmit={submit} className="space-y-4">
                        {mode === "register" && (
                            <div className="space-y-1.5">
                                <label htmlFor="display_name" className="text-xs font-medium">
                                    昵称 <span className="text-muted-foreground">（可选）</span>
                                </label>
                                <input
                                    id="display_name"
                                    value={displayName}
                                    onChange={(event) => setDisplayName(event.target.value)}
                                    autoComplete="nickname"
                                    maxLength={40}
                                    placeholder="怎么称呼你"
                                    className="w-full rounded-lg border bg-card px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10"
                                />
                            </div>
                        )}

                        <div className="space-y-1.5">
                            <label htmlFor="email" className="text-xs font-medium">
                                邮箱
                            </label>
                            <input
                                id="email"
                                type="email"
                                required
                                autoComplete="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                placeholder="you@example.com"
                                className="w-full rounded-lg border bg-card px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label htmlFor="password" className="text-xs font-medium">
                                密码
                            </label>
                            <div className="relative">
                                <input
                                    id="password"
                                    type={showPassword ? "text" : "password"}
                                    required
                                    minLength={8}
                                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                                    value={password}
                                    onChange={(event) => setPassword(event.target.value)}
                                    placeholder={mode === "register" ? "至少 8 位" : "输入密码"}
                                    className="w-full rounded-lg border bg-card px-3 py-2.5 pr-10 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword((value) => !value)}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground transition-colors hover:text-foreground"
                                    aria-label={showPassword ? "隐藏密码" : "显示密码"}
                                >
                                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                                </button>
                            </div>
                        </div>

                        {mode === "register" && (
                            <div className="space-y-1.5">
                                <label htmlFor="confirm" className="text-xs font-medium">
                                    确认密码
                                </label>
                                <input
                                    id="confirm"
                                    type={showPassword ? "text" : "password"}
                                    required
                                    minLength={8}
                                    autoComplete="new-password"
                                    value={confirm}
                                    onChange={(event) => setConfirm(event.target.value)}
                                    placeholder="再输一次"
                                    className="w-full rounded-lg border bg-card px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/10"
                                />
                            </div>
                        )}

                        {error && (
                            <p className="rounded-lg border border-destructive/25 bg-destructive/5 px-3 py-2 text-xs leading-relaxed text-destructive">
                                {error}
                            </p>
                        )}

                        <button
                            type="submit"
                            disabled={busy}
                            className="group flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-transform active:scale-[0.985] disabled:opacity-60"
                        >
                            {busy ? (
                                <Loader2 className="size-4 animate-spin" />
                            ) : (
                                <>
                                    {mode === "login" ? "登录" : "注册并登录"}
                                    <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                                </>
                            )}
                        </button>
                    </form>

                    <p className="mt-6 text-center text-[11px] leading-relaxed text-muted-foreground">
                        登录即表示你知道这是个人项目，
                        <br />
                        数据只存在你自己的 PostgreSQL 与 Milvus 里。
                    </p>
                </div>
            </section>
        </main>
    );
}
