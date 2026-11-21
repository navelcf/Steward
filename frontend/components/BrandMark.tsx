import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/cn";

// 品牌标记：石墨底 + 盾牌，和登录页、侧栏、助手头像共用同一个符号。
export default function BrandMark({ className }: { className?: string }) {
    return (
        <div
            className={cn(
                "flex shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm",
                className
            )}
        >
            <ShieldCheck className="size-[58%]" strokeWidth={2.2} />
        </div>
    );
}
