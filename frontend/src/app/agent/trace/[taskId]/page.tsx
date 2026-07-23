"use client";

import AgentTraceDAG from "@/components/agent-trace/DAGView";
import PageHeader from "@/components/layout/PageHeader";
import { useParams } from "next/navigation";

export default function AgentTracePage() {
  const { taskId } = useParams<{ taskId: string }>();
  return (
    <div>
      <PageHeader
        title="Agent 执行链路"
        description={`任务 ${taskId} 的真实调度、执行状态与工具调用详情`}
        backTo="/agent/chat"
      />
      <AgentTraceDAG taskId={taskId} />
    </div>
  );
}
