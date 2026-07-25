"use client";

import { useEffect, useState } from "react";
import { Card, Row, Col, Tag, Timeline, Statistic, Spin, Alert, Button } from "antd";
import {
  TeamOutlined, ExperimentOutlined, ShoppingOutlined,
  SafetyOutlined, FileTextOutlined, DashboardOutlined,
  CheckCircleOutlined, ClockCircleOutlined,
} from "@ant-design/icons";
import { apiFetch } from "@/api/fetch";
import PageHeader from "@/components/layout/PageHeader";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

const ICON_MAP: Record<string, React.ReactNode> = {
  "👔": <TeamOutlined style={{ fontSize: 28, color: "#1677ff" }} />,
  "🔬": <ExperimentOutlined style={{ fontSize: 28, color: "#722ed1" }} />,
  "💼": <ShoppingOutlined style={{ fontSize: 28, color: "#52c41a" }} />,
  "🛡️": <SafetyOutlined style={{ fontSize: 28, color: "#fa8c16" }} />,
  "📋": <FileTextOutlined style={{ fontSize: 28, color: "#13c2c2" }} />,
  "📊": <DashboardOutlined style={{ fontSize: 28, color: "#eb2f96" }} />,
};

const STATUS_COLOR: Record<string, string> = {
  active: "#52c41a", idle: "#1677ff", running: "#fa8c16",
};

export default function AgentTeamPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch(`${API}/agent/team/status`)
      .then((r) => r.json())
      .then((d) => setData(d.data))
      .catch((e) => setError(e.message || "无法获取Agent团队状态"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: "block", margin: "60px auto" }} />;
  if (error) return <Alert type="error" message="Agent团队状态获取失败" description={error}
    style={{ margin: 24 }} action={<Button onClick={() => window.location.reload()}>重试</Button>} />;
  if (!data) return <Alert type="warning" message="暂无Agent数据" style={{ margin: 24 }} />;

  const agents = data.agents || {};

  return (
    <div>
      <PageHeader
        title="AI 产业运营团队"
        description="查看各业务 Agent 的在线状态、能力与最近任务"
        backLabel="返回园区总览"
        extra={
          <Tag color="green" style={{ fontSize: 14, padding: "4px 12px" }}>
            全部 Agent 在线 · 今日已完成 {data.total_tasks_today} 个任务
          </Tag>
        }
      />

      {/* Agent Cards */}
      <Row gutter={[16, 16]}>
        {Object.entries(agents).map(([name, info]: [string, any]) => (
          <Col span={8} key={name}>
            <Card
              hoverable
              style={{ borderTop: `3px solid ${STATUS_COLOR[info.status] || "#1677ff"}` }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                {ICON_MAP[info.icon] || <TeamOutlined />}
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{info.display}</div>
                  <div style={{ fontSize: 12, color: "#999" }}>{name}</div>
                </div>
                <Tag color={info.status === "active" ? "green" : "blue"} style={{ marginLeft: "auto" }}>
                  {info.status === "active" ? "运行中" : "待命"}
                </Tag>
              </div>
              <div style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>
                最近任务: {info.last_task}
              </div>
              <Row gutter={8}>
                <Col span={8}>
                  <Statistic title="耗时" value={`${(info.last_execution_ms / 1000).toFixed(1)}s`} valueStyle={{ fontSize: 14 }} />
                </Col>
                <Col span={8}>
                  <Statistic title="今日任务" value={info.tasks_today} valueStyle={{ fontSize: 14 }} />
                </Col>
                <Col span={8}>
                  <Statistic title="能力数" value={info.capabilities?.length || 0} valueStyle={{ fontSize: 14 }} />
                </Col>
              </Row>
              <div style={{ marginTop: 8 }}>
                {info.capabilities?.slice(0, 3).map((c: string) => (
                  <Tag key={c} style={{ fontSize: 11, marginBottom: 4 }}>{c}</Tag>
                ))}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Execution Timeline */}
      <Card title="Agent 协作时间线" style={{ marginTop: 24 }}>
        <Timeline
          items={[
            { color: "blue", children: <><Tag color="blue">Supervisor</Tag> 意图识别 + 任务规划 (450ms)</> },
            { color: "purple", children: <><Tag color="purple">IndustryAgent</Tag> 产业趋势分析 (2.5s)</> },
            { color: "green", children: <><Tag color="green">InvestmentAgent</Tag> 企业搜索+评分 (3.2s) — <Tag color="orange">RiskAgent</Tag> 风险评估 (1.8s) 并行执行</> },
            { color: "cyan", children: <><Tag color="cyan">PolicyAgent</Tag> 政策匹配 (1.5s)</> },
            { color: "magenta", children: <><Tag color="magenta">BIAgent</Tag> Dashboard 数据聚合 (0.8s)</> },
            { color: "blue", children: <><Tag color="blue">Supervisor</Tag> 结果聚合 → 生成报告 (12.7s)</> },
          ]}
        />
      </Card>
    </div>
  );
}
