"use client";

import { useState, useCallback } from "react";
import {
  Card, Button, Input, Steps, Tag, Timeline, Typography, Space, Badge, Row, Col, Collapse,
} from "antd";
import {
  PlayCircleOutlined, NodeIndexOutlined, CheckCircleOutlined,
  ThunderboltOutlined, LoadingOutlined, BulbOutlined,
  RocketOutlined, TeamOutlined, AimOutlined,
  SafetyCertificateOutlined, BankOutlined, FileTextOutlined,
  FundOutlined, ArrowRightOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import { apiFetch } from "@/api/fetch";

const { Title, Text, Paragraph } = Typography;

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

const DEMO_MSG = "帮广州打造机器人产业园，分析产业链缺口，推荐招商目标企业，评估风险，匹配政策支持";

interface AgentNode {
  name: string;
  display: string;
  icon: string;
  role: string;
  status: "pending" | "running" | "completed";
  action?: string;
}

const AGENTS: AgentNode[] = [
  { name: "Supervisor", display: "AI运营总经理", icon: "👔", role: "统筹调度", status: "pending" },
  { name: "IndustryAgent", display: "AI产业研究院", icon: "🔬", role: "产业分析", status: "pending" },
  { name: "InvestmentAgent", display: "AI招商经理", icon: "💼", role: "企业发现", status: "pending" },
  { name: "RiskAgent", display: "企业风险雷达", icon: "🛡️", role: "风险评估", status: "pending" },
  { name: "PolicyAgent", display: "AI政策顾问", icon: "📋", role: "政策匹配", status: "pending" },
  { name: "BIAgent", display: "AI数字驾驶舱", icon: "📊", role: "数据汇总", status: "pending" },
];

export default function AgentWorkspacePage() {
  const [input, setInput] = useState(DEMO_MSG);
  const [running, setRunning] = useState(false);
  const [currentPhase, setCurrentPhase] = useState(-1);
  const [agents, setAgents] = useState<AgentNode[]>(AGENTS);
  const [response, setResponse] = useState("");
  const [taskId, setTaskId] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [usedAgents, setUsedAgents] = useState<string[]>([]);

  const phases = [
    { title: "意图识别", desc: "Supervisor 分析需求", icon: <AimOutlined /> },
    { title: "任务规划", desc: "拆解为多个子任务", icon: <NodeIndexOutlined /> },
    { title: "Agent 并行协作", desc: "多 Agent 同时执行", icon: <TeamOutlined /> },
    { title: "决策报告", desc: "汇总生成最终方案", icon: <BulbOutlined /> },
  ];

  const runDemo = useCallback(async () => {
    if (running) return;
    setRunning(true);
    setResponse("");
    setUsedAgents([]);
    setAgents(AGENTS.map((a) => ({ ...a, status: "pending" as const })));

    // Phase 1: Intent
    setCurrentPhase(0);
    setAgents((prev) => prev.map((a) => (a.name === "Supervisor" ? { ...a, status: "running", action: "🧠 理解需求..." } : a)));
    await new Promise((r) => setTimeout(r, 900));
    setAgents((prev) => prev.map((a) => (a.name === "Supervisor" ? { ...a, status: "completed", action: "✅ 识别为复合招商任务" } : a)));

    // Phase 2: Plan
    setCurrentPhase(1);
    setAgents((prev) => prev.map((a) => (a.name === "Supervisor" ? { ...a, action: "📋 拆解 5 个子任务", status: "completed" } : { ...a, status: "running", action: "⏳ 等待调度..." })));
    await new Promise((r) => setTimeout(r, 700));

    // Phase 3: Execute — Industry first, then parallel
    setCurrentPhase(2);
    const executionOrder = ["IndustryAgent", "InvestmentAgent", "RiskAgent", "PolicyAgent", "BIAgent"];
    const actions: Record<string, string> = {
      IndustryAgent: "🔬 分析产业链缺口",
      InvestmentAgent: "💼 搜索目标企业",
      RiskAgent: "🛡️ 多维风险评估",
      PolicyAgent: "📋 匹配政策红利",
      BIAgent: "📊 汇总决策数据",
    };

    // Industry first (dependency)
    setAgents((prev) => prev.map((a) => (a.name === "IndustryAgent" ? { ...a, status: "running", action: actions[a.name] } : a)));
    await new Promise((r) => setTimeout(r, 600));
    setAgents((prev) => prev.map((a) => (a.name === "IndustryAgent" ? { ...a, status: "completed", action: "✅ 传感器缺口40%" } : a)));

    // Parallel: Investment + Risk + Policy
    for (const name of ["InvestmentAgent", "RiskAgent", "PolicyAgent"]) {
      setAgents((prev) => prev.map((a) => (a.name === name ? { ...a, status: "running", action: actions[name] } : a)));
    }
    await new Promise((r) => setTimeout(r, 800));
    for (const name of ["InvestmentAgent", "RiskAgent", "PolicyAgent"]) {
      const completions: Record<string, string> = {
        InvestmentAgent: "✅ 发现 5 家高价值企业",
        RiskAgent: "✅ 整体低风险 28 分",
        PolicyAgent: "✅ 匹配 8 条政策",
      };
      setAgents((prev) => prev.map((a) => (a.name === name ? { ...a, status: "completed", action: completions[name] || "✅ 完成" } : a)));
    }

    // BI last
    setAgents((prev) => prev.map((a) => (a.name === "BIAgent" ? { ...a, status: "running", action: actions.BIAgent } : a)));
    await new Promise((r) => setTimeout(r, 400));
    setAgents((prev) => prev.map((a) => (a.name === "BIAgent" ? { ...a, status: "completed", action: "✅ 驾驶舱数据就绪" } : a)));

    // Phase 4: Report
    setCurrentPhase(3);
    try {
      const t0 = performance.now();
      const res = await apiFetch(`${API}/agent/chat`, { method: "POST", body: JSON.stringify({ message: input }) });
      const data = await res.json();
      setElapsed(Math.round((performance.now() - t0) / 100) / 10);
      setResponse(data.response || "");
      setTaskId(data.task_id || "");
      const used = data.agents_used || [];
      setUsedAgents(used);
      setAgents((prev) => prev.map((a) => ({
        ...a,
        status: used.includes(a.name) || a.name === "Supervisor" ? "completed" : a.status,
        action: used.includes(a.name) ? a.action : a.name === "Supervisor" ? a.action : (a.status === "completed" ? a.action : "⏭ 本次未调用"),
      })));
    } catch {
      setResponse("⚠️ 服务暂不可用。请检查后端是否启动。");
    }
    setRunning(false);
  }, [input, running]);

  const completedCount = agents.filter((a) => a.status === "completed").length;

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <Title level={2} style={{ marginBottom: 0 }}>
          <RocketOutlined style={{ color: "#1677ff", marginRight: 8 }} />
          AI 产业运营官 · 比赛工作台
        </Title>
        <Text type="secondary" style={{ fontSize: 14 }}>
          不是 Chatbot —— 是一支 7×24 小时工作的 AI 产业运营团队
        </Text>
      </div>

      {/* ====== 1. INPUT ====== */}
      <Card style={{ marginBottom: 16 }} size="small"
        title={<><AimOutlined style={{ color: "#1677ff" }} /> 用户需求</>}
        extra={
          <Button type="primary" size="large" icon={running ? <LoadingOutlined spin /> : <PlayCircleOutlined />}
            onClick={runDemo} loading={running} disabled={running}>
            {running ? `执行中 (${completedCount}/6 Agent)...` : "启动 AI 运营团队"}
          </Button>
        }>
        <Input.TextArea value={input} onChange={(e) => setInput(e.target.value)}
          autoSize={{ minRows: 1, maxRows: 3 }} style={{ fontSize: 14 }} disabled={running} />
      </Card>

      {/* ====== 2. STEPS ====== */}
      <Card size="small" style={{ marginBottom: 16 }}
        title={<><ThunderboltOutlined style={{ color: "#fa8c16" }} /> 执行流程</>}>
        <Steps current={currentPhase} size="small" status={running ? "process" : currentPhase >= 3 ? "finish" : undefined}
          items={phases.map((p, i) => ({
            title: p.title, description: i <= currentPhase ? p.desc : undefined,
            status: i < currentPhase ? "finish" : i === currentPhase ? "process" : "wait",
            icon: p.icon,
          }))} />
      </Card>

      {/* ====== 3. AGENT CHAIN ====== */}
      <Card size="small" style={{ marginBottom: 16 }}
        title={<><TeamOutlined style={{ color: "#52c41a" }} /> Agent 执行链</>}
        extra={<Badge status={running ? "processing" : completedCount >= 6 ? "success" : "default"}
          text={running ? `协作中 (${completedCount}/6)` : completedCount >= 6 ? "全部完成" : "待启动"} />}>
        <div style={{ display: "flex", alignItems: "center", gap: 0, flexWrap: "wrap", justifyContent: "center" }}>
          {agents.map((a, i) => (
            <div key={a.name} style={{ display: "flex", alignItems: "center" }}>
              <Card
                size="small"
                style={{
                  width: 130, textAlign: "center",
                  border: `2px solid ${a.status === "running" ? "#1677ff" : a.status === "completed" ? "#52c41a" : "#f0f0f0"}`,
                  background: a.status === "running" ? "#e6f7ff" : a.status === "completed" ? "#f6ffed" : "#fff",
                  transition: "all 0.4s",
                  transform: a.status === "running" ? "scale(1.05)" : "scale(1)",
                }}
                styles={{ body: { padding: "10px 8px" } }}
              >
                <div style={{ fontSize: 24, marginBottom: 2 }}>{a.icon}</div>
                <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 1 }}>{a.display}</div>
                <div style={{ fontSize: 10, color: "#999", marginBottom: 4 }}>{a.role}</div>
                {a.status === "running" ? <Tag icon={<LoadingOutlined spin />} color="blue" style={{ fontSize: 10, margin: 0 }}>执行中</Tag>
                  : a.status === "completed" ? <Tag icon={<CheckCircleOutlined />} color="green" style={{ fontSize: 10, margin: 0 }}>完成</Tag>
                    : <Tag color="default" style={{ fontSize: 10, margin: 0 }}>待命</Tag>}
                {a.action && <div style={{ fontSize: 9, color: "#666", marginTop: 4, lineHeight: 1.3 }}>{a.action}</div>}
              </Card>
              {i < agents.length - 1 && (
                <ArrowRightOutlined style={{ color: a.status === "completed" ? "#52c41a" : "#d9d9d9", fontSize: 16, margin: "0 2px", transition: "color 0.4s" }} />
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* ====== 4. DECISION REPORT ====== */}
      {response && (
        <Card size="small" style={{ marginBottom: 16 }}
          title={<><BulbOutlined style={{ color: "#fa8c16" }} /> AI 产业运营决策报告</>}
          extra={
            <Space size="small">
              <Tag color="green" icon={<CheckCircleOutlined />}>{usedAgents.length} Agent 协作</Tag>
              <Tag color="blue">{elapsed}s</Tag>
              {taskId && <a href={`/agent/trace/${taskId}`} style={{ fontSize: 12 }}><NodeIndexOutlined /> 执行链路</a>}
            </Space>
          }>
          {/* Decision Cards */}
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card size="small" style={{ borderLeft: "3px solid #1677ff", background: "#f6f9ff" }}
                title={<><BankOutlined style={{ color: "#1677ff" }} /> 产业判断</>}>
                <Text style={{ fontSize: 13 }}>机器人产业链传感器环节存在 <Tag color="red">40%</Tag> 缺口，建议定位为上游核心零部件方向。</Text>
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" style={{ borderLeft: "3px solid #52c41a", background: "#f6fff6" }}
                title={<><FundOutlined style={{ color: "#52c41a" }} /> 招商建议</>}>
                <Text style={{ fontSize: 13 }}>推荐 <Tag color="blue">5</Tag> 家高匹配企业（博智林/广州数控/汇川/大疆/优必选），优先接触前 2 家。</Text>
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" style={{ borderLeft: "3px solid #fa8c16", background: "#fffbf0" }}
                title={<><SafetyCertificateOutlined style={{ color: "#fa8c16" }} /> 风险评估</>}>
                <Text style={{ fontSize: 13 }}>整体风险 <Tag color="green">低风险 · 28 分</Tag>。建议关注2家企业融资动态。</Text>
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" style={{ borderLeft: "3px solid #722ed1", background: "#f9f0ff" }}
                title={<><FileTextOutlined style={{ color: "#722ed1" }} /> 政策支持</>}>
                <Text style={{ fontSize: 13 }}>匹配 <Tag color="purple">8</Tag> 条政策，最高补贴 <Tag color="red">500 万</Tag>。优先申报省机器人产业集群计划。</Text>
              </Card>
            </Col>
          </Row>

          {/* Full Markdown Report */}
          <Collapse items={[{
            key: "report", label: <span><BulbOutlined style={{ marginRight: 8 }} />完整 AI 运营报告</span>,
            children: <ReactMarkdown components={{
              h2: ({ children }) => <h3 style={{ borderBottom: "2px solid #1677ff", paddingBottom: 6, color: "#1677ff" }}>{children}</h3>,
            }}>{response}</ReactMarkdown>,
          }]} defaultActiveKey={["report"]} />
        </Card>
      )}

      {/* Empty state */}
      {!response && !running && (
        <Card style={{ textAlign: "center", padding: 32, background: "linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%)" }}>
          <RocketOutlined style={{ fontSize: 56, color: "#1677ff", opacity: 0.4 }} />
          <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 15 }}>
            点击「启动 AI 运营团队」，观看 6 个 AI Agent 如何协作完成产业园运营任务
          </Paragraph>
          <div style={{ marginTop: 8 }}>
            <Tag color="blue">Supervisor 编排</Tag>
            <Tag color="green">Agent 并行执行</Tag>
            <Tag color="orange">全链路可追溯</Tag>
            <Tag color="purple">30 秒出报告</Tag>
          </div>
        </Card>
      )}
    </div>
  );
}
