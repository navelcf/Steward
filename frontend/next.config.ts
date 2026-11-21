import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    /* config options here */
    cacheComponents: true,
    partialPrefetching: true,
    // 开发时同时允许 localhost 和 127.0.0.1：否则 127.0.0.1 打开页面会被判成跨源，
    // /_next 的脚本请求被拦，表现就是「页面能看见但完全不交互、接口也不发」。
    allowedDevOrigins: ["127.0.0.1", "localhost"],
    turbopack: {
        rules: {
            "*.css": {
                loaders: ["@tailwindcss/turbopack"],
                as: "*.css",
            },
        },
    },
};

export default nextConfig;
