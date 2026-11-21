import { clsx, type ClassValue } from "clsx";

// 条件 class 的统一入口，避免到处写模板字符串。
export function cn(...inputs: ClassValue[]): string {
    return clsx(inputs);
}
