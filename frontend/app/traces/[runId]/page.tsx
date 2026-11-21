import TraceView from "./TraceView";

// 这条路由依赖运行时参数（run_id），不参与静态预渲染。
export const instant = false;

// 服务端只负责把动态段解出来，再交给客户端组件去读 localStorage 里的 token。
export default async function TracePage({ params }: { params: Promise<{ runId: string }> }) {
    const { runId } = await params;
    return <TraceView runId={runId} />;
}
