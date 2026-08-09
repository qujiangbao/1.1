"use client";

import { useEffect, useState } from "react";
import { Card, Tag, Drawer, Descriptions, Badge, Alert, Spin } from "antd";
import {
  UserOutlined, DeploymentUnitOutlined, ExperimentOutlined,
  ShoppingOutlined, SafetyOutlined, FileTextOutlined,
  DashboardOutlined, ApiOutlined, CheckCircleOutlined,
  LoadingOutlined, ClockCircleOutlined,
} from "@ant-design/icons";
import { apiJson } from "@/api/fetch";

// DAG node types
interface DAGNode {
  id: string;
  label: string;
  type: "user" | "supervisor" | "agent" | "tool" | "result";
  agent?: string;
  action?: string;
  status: "pending" | "running" | "completed" | "failed";
  duration_ms?: number;
  x: number;
  y: number;
  input?: string;
  output?: string;
  tools?: string[];
}

interface DAGEdge {
  from: string;
  to: string;
  label?: string;
  parallel?: boolean;
}

// Sample DAG data for Champion Demo
function buildChampionDAG(): { nodes: DAGNode[]; edges: DAGEdge[] } {
  const nodes: DAGNode[] = [
    {
      id: "user", label: "用户需求", type: "user",
      status: "completed",
      x: 360, y: 20,
      input: "帮我制定广州机器人产业园招商方案",
    },
    {
      id: "supervisor", label: "Supervisor", type: "supervisor",
      agent: "AI运营总经理", action: "意图识别 + 任务规划",
      status: "completed", duration_ms: 450,
      x: 360, y: 120,
      output: "意图: compound | 规划: 5 Agent 协作",
    },
    {
      id: "industry", label: "IndustryAgent", type: "agent",
      agent: "AI产业研究院", action: "产业趋势分析",
      status: "completed", duration_ms: 2500,
      x: 120, y: 240,
      output: "趋势评分: 85 (战略产业) | 产业链缺口: 传感器40%",
      tools: ["industry_query", "knowledge_graph_query"],
    },
    {
      id: "investment", label: "InvestmentAgent", type: "agent",
      agent: "AI招商经理", action: "企业搜索+画像+评分",
      status: "completed", duration_ms: 3200,
      x: 360, y: 240,
      output: "搜索45家企业 | Top5推荐",
      tools: ["enterprise_search", "enterprise_profile_get", "investment_scoring"],
    },
    {
      id: "risk", label: "RiskAgent", type: "agent",
      agent: "企业风险雷达", action: "批量风险评估",
      status: "completed", duration_ms: 1800,
      x: 540, y: 370,
      output: "评分: 28 LOW | 3家需关注",
      tools: ["risk_scoring", "risk_history"],
    },
    {
      id: "policy", label: "PolicyAgent", type: "agent",
      agent: "AI政策顾问", action: "政策匹配",
      status: "completed", duration_ms: 1500,
      x: 180, y: 370,
      output: "匹配8条政策 | 最高匹配度95%",
      tools: ["policy_vector_search", "policy_metadata_search"],
    },
    {
      id: "bi", label: "BIAgent", type: "agent",
      agent: "AI经营分析师", action: "园区经营指标聚合",
      status: "completed", duration_ms: 800,
      x: 360, y: 500,
      output: "KPI数据就绪",
      tools: ["dashboard_query"],
    },
    {
      id: "result", label: "最终报告", type: "result",
      status: "completed",
      x: 360, y: 600,
      output: "广州机器人产业园招商策略方案 (1583字)",
    },
  ];

  const edges: DAGEdge[] = [
    { from: "user", to: "supervisor" },
    { from: "supervisor", to: "industry" },
    { from: "industry", to: "investment" },
    { from: "investment", to: "risk", label: "并行", parallel: true },
    { from: "investment", to: "policy", label: "并行", parallel: true },
    { from: "risk", to: "bi" },
    { from: "policy", to: "bi" },
    { from: "bi", to: "result" },
  ];

  return { nodes, edges };
}

function buildLiveDAG(trace: any): { nodes: DAGNode[]; edges: DAGEdge[] } {
  const apiNodes = Array.isArray(trace?.nodes) ? trace.nodes : [];
  const agentNodes = apiNodes.filter((node: any) => node.id !== "supervisor");
  const nodes: DAGNode[] = [
    { id: "user", label: "用户需求", type: "user", status: "completed", x: 360, y: 20 },
    { id: "supervisor", label: "Supervisor", type: "supervisor", status: "completed", x: 360, y: 120 },
    ...agentNodes.map((node: any, index: number) => ({
      id: node.id,
      label: node.label,
      type: "agent" as const,
      agent: node.label,
      status: node.status === "failed" ? "failed" as const : "completed" as const,
      duration_ms: node.execution_time_ms || 0,
      output: node.result || "执行完成",
      x: index % 2 === 0 ? 220 : 500,
      y: 240 + Math.floor(index / 2) * 135,
    })),
  ];
  const resultY = 260 + Math.max(1, Math.ceil(agentNodes.length / 2)) * 135;
  nodes.push({
    id: "result", label: "最终报告", type: "result", status: "completed", x: 360, y: resultY,
    output: `任务状态: ${trace?.status || "completed"}`,
  });

  const known = new Set(nodes.map((node) => node.id));
  const apiEdges: DAGEdge[] = (trace?.edges || [])
    .filter((edge: any) => known.has(edge.from) && known.has(edge.to))
    .map((edge: any) => ({ from: edge.from, to: edge.to }));
  const leaves = agentNodes.filter((node: any) => !apiEdges.some((edge) => edge.from === node.id));
  return {
    nodes,
    edges: [
      { from: "user", to: "supervisor" },
      ...apiEdges,
      ...(leaves.length ? leaves.map((node: any) => ({ from: node.id, to: "result" })) : [{ from: "supervisor", to: "result" }]),
    ],
  };
}

// P3: 从 SSE 事件构建实时 DAG
const TYPE_STYLE: Record<string, { color: string; icon: React.ReactNode; bg: string }> = {
  user:       { color: "#8c8c8c", icon: <UserOutlined />,        bg: "#fafafa" },
  supervisor: { color: "#1677ff", icon: <DeploymentUnitOutlined />, bg: "#e6f4ff" },
  agent:      { color: "#52c41a", icon: <CheckCircleOutlined />, bg: "#f6ffed" },
  tool:       { color: "#fa8c16", icon: <ApiOutlined />,          bg: "#fff7e6" },
  result:     { color: "#722ed1", icon: <DashboardOutlined />,   bg: "#f9f0ff" },
};

const AGENT_ICON: Record<string, React.ReactNode> = {
  IndustryAgent: <ExperimentOutlined />,
  InvestmentAgent: <ShoppingOutlined />,
  RiskAgent: <SafetyOutlined />,
  PolicyAgent: <FileTextOutlined />,
  BIAgent: <DashboardOutlined />,
};

function DAGNodeCard({
  node, onClick, isSelected,
}: {
  node: DAGNode; onClick: () => void; isSelected: boolean;
}) {
  const style = TYPE_STYLE[node.type] || TYPE_STYLE.agent;
  const w = node.type === "user" || node.type === "result" ? 200 : 220;

  return (
    <div style={{ position: "absolute", left: node.x - w / 2, top: node.y, width: w, zIndex: isSelected ? 10 : 1 }}>
      <div
        onClick={onClick}
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: `2px solid ${isSelected ? style.color : "#d9d9d9"}`,
          background: style.bg,
          cursor: "pointer",
          transition: "all 0.2s",
          boxShadow: isSelected ? `0 2px 8px ${style.color}40` : "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ color: style.color, fontSize: 18 }}>
            {AGENT_ICON[node.agent || ""] || style.icon}
          </span>
          <span style={{ fontWeight: 700, fontSize: 13, flex: 1 }}>{node.label}</span>
          <Badge
            status={node.status === "completed" ? "success" : node.status === "running" ? "processing" : node.status === "failed" ? "error" : "default"}
          />
        </div>
        {node.action && (
          <div style={{ fontSize: 11, color: "#666", marginBottom: 2 }}>{node.action}</div>
        )}
        {node.duration_ms && (
          <Tag color="blue" style={{ fontSize: 10, margin: 0 }}>
            {node.duration_ms > 1000 ? `${(node.duration_ms / 1000).toFixed(1)}s` : `${node.duration_ms}ms`}
          </Tag>
        )}
        {node.tools && node.tools.length > 0 && (
          <div style={{ marginTop: 4 }}>
            {node.tools.map((t) => (
              <Tag key={t} color="orange" style={{ fontSize: 10, margin: "1px 2px" }}>{t}</Tag>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SVGEdge({ edge, nodes }: { edge: DAGEdge; nodes: DAGNode[] }) {
  const from = nodes.find((n) => n.id === edge.from);
  const to = nodes.find((n) => n.id === edge.to);
  if (!from || !to) return null;

  const x1 = from.x;
  const y1 = from.y + 60;
  const x2 = to.x;
  const y2 = to.y;

  const midY = (y1 + y2) / 2;

  return (
    <g>
      <path
        d={`M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`}
        fill="none"
        stroke={edge.parallel ? "#fa8c16" : "#1677ff"}
        strokeWidth={edge.parallel ? 2 : 2.5}
        strokeDasharray={edge.parallel ? "6,4" : "none"}
        markerEnd={`url(#${edge.parallel ? "arrowhead-parallel" : "arrowhead-default"})`}
        opacity={0.7}
      />
      {edge.parallel && (
        <text x={(x1 + x2) / 2 + 10} y={midY - 6} fontSize={11} fill="#fa8c16" fontWeight={600}>
          {edge.label || "并行"}
        </text>
      )}
      {!edge.parallel && edge.label && (
        <text x={(x1 + x2) / 2 + 8} y={midY - 6} fontSize={10} fill="#1677ff">
          {edge.label}
        </text>
      )}
    </g>
  );
}

export default function AgentTraceDAG({ taskId }: { taskId?: string }) {
  const [dag, setDag] = useState(() => buildChampionDAG());
  const [selectedNode, setSelectedNode] = useState<DAGNode | null>(null);
  const [loading, setLoading] = useState(Boolean(taskId));
  const [error, setError] = useState("");

  useEffect(() => {
    if (!taskId) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    apiJson<unknown>(
      `${process.env.NEXT_PUBLIC_API_URL || "/api/v1"}/agent/task/${taskId}/trace`,
      { signal: controller.signal },
    )
      .then((trace) => setDag(buildLiveDAG(trace)))
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "执行链路加载失败");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [taskId]);

  const svgH = Math.max(680, ...dag.nodes.map((node) => node.y + 100));
  const svgW = 750;

  return (
    <div>
      <h2 style={{ marginBottom: 4 }}>
        Agent Trace — DAG 可视化
      </h2>
      <p style={{ color: "#999", marginBottom: 16, fontSize: 13 }}>
        点击节点查看详情 · 蓝色=串行 · 橙色虚线=并行
      </p>
      {loading && <Spin style={{ display: "block", margin: "24px auto" }} />}
      {error && <Alert type="error" showIcon message="执行链路加载失败" description={error} style={{ marginBottom: 16 }} />}

      {!loading && <Card>
        <div style={{ overflow: "auto" }}>
          {/* SVG edges and HTML nodes must share the same coordinate origin. */}
          <div style={{ position: "relative", width: svgW, height: svgH, margin: "0 auto" }}>
            <svg
              width={svgW}
              height={svgH}
              style={{ position: "absolute", inset: 0, display: "block" }}
              aria-label="Agent 执行链路图"
            >
              <defs>
                <marker id="arrowhead-default" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                  <polygon points="0 0, 8 3, 0 6" fill="#1677ff" />
                </marker>
                <marker id="arrowhead-parallel" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                  <polygon points="0 0, 8 3, 0 6" fill="#fa8c16" />
                </marker>
              </defs>

              {/* Legend */}
              <g transform="translate(10, 10)">
                {Object.entries(TYPE_STYLE).filter(([k]) => k !== "tool").map(([key, style], i) => (
                  <g key={key} transform={`translate(${i * 120}, 0)`}>
                    <rect width={14} height={14} rx={3} fill={style.color} opacity={0.3} />
                    <rect x={1} y={1} width={12} height={12} rx={2} fill={style.color} />
                    <text x={20} y={12} fontSize={11} fill="#666">
                      {key === "user" ? "用户" : key === "supervisor" ? "调度" : key === "agent" ? "Agent" : "结果"}
                    </text>
                  </g>
                ))}
              </g>

              {/* Edges */}
              {dag.edges.map((e) => (
                <SVGEdge key={`${e.from}-${e.to}`} edge={e} nodes={dag.nodes} />
              ))}
            </svg>

            {/* Nodes share the SVG canvas coordinate system. */}
            {dag.nodes.map((node) => (
              <DAGNodeCard
                key={node.id}
                node={node}
                isSelected={selectedNode?.id === node.id}
                onClick={() => setSelectedNode(selectedNode?.id === node.id ? null : node)}
              />
            ))}
          </div>
        </div>
      </Card>}

      {/* Detail Drawer */}
      <Drawer
        title={selectedNode ? `${selectedNode.label} 详情` : ""}
        open={!!selectedNode}
        onClose={() => setSelectedNode(null)}
        width={400}
      >
        {selectedNode && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="类型">
              <Tag color={TYPE_STYLE[selectedNode.type]?.color}>{selectedNode.type}</Tag>
            </Descriptions.Item>
            {selectedNode.agent && (
              <Descriptions.Item label="Agent">{selectedNode.agent}</Descriptions.Item>
            )}
            {selectedNode.action && (
              <Descriptions.Item label="动作">{selectedNode.action}</Descriptions.Item>
            )}
            <Descriptions.Item label="状态">
              <Badge status={selectedNode.status === "completed" ? "success" : selectedNode.status === "running" ? "processing" : "error"}
                text={selectedNode.status === "completed" ? "完成" : selectedNode.status === "running" ? "执行中" : "失败"} />
            </Descriptions.Item>
            {selectedNode.duration_ms && (
              <Descriptions.Item label="耗时">
                {selectedNode.duration_ms > 1000
                  ? `${(selectedNode.duration_ms / 1000).toFixed(1)}s`
                  : `${selectedNode.duration_ms}ms`}
              </Descriptions.Item>
            )}
            {selectedNode.input && (
              <Descriptions.Item label="输入">
                <code style={{ fontSize: 11 }}>{selectedNode.input}</code>
              </Descriptions.Item>
            )}
            {selectedNode.output && (
              <Descriptions.Item label="输出">
                <code style={{ fontSize: 11 }}>{selectedNode.output}</code>
              </Descriptions.Item>
            )}
            {selectedNode.tools && (
              <Descriptions.Item label="Tool调用">
                {selectedNode.tools.map((t) => <Tag key={t} color="orange">{t}</Tag>)}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
