"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, Row, Col, Tag, Timeline, Statistic, Spin, Alert, Button } from "antd";
import {
  TeamOutlined, ExperimentOutlined, ShoppingOutlined,
  SafetyOutlined, FileTextOutlined, DashboardOutlined,
  NodeIndexOutlined,
} from "@ant-design/icons";
import { apiJson } from "@/api/fetch";
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

const AGENT_ACTIONS: Record<string, { path: string; label: string; tip: string }> = {
  Supervisor:        { path: "/agent/workspace",                  label: "启动任务",    tip: "在园区决策工作台中调度全团队执行产业分析任务" },
  IndustryAgent:     { path: "/agent/chat",                       label: "产业分析",    tip: "向产业研究院提问产业链趋势与缺口" },
  InvestmentAgent:   { path: "/dashboard/investment",             label: "招商寻商",    tip: "进入招商决策中心寻找目标企业" },
  RiskAgent:         { path: "/dashboard/risk",                   label: "风险看板",    tip: "查看企业风险评估记录与分布" },
  PolicyAgent:       { path: "/management/policies",              label: "政策查询",    tip: "查看和管理产业政策正文与申报条件" },
  BIAgent:           { path: "/dashboard/bi",                     label: "经营分析",    tip: "查看园区运营指标与趋势图表" },
  EnterpriseServiceAgent: { path: "/agent/chat",                  label: "服务咨询",    tip: "识别企业诉求并给出人工办理清单，不会虚构工单" },
};

export default function AgentTeamPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await apiJson<{ success: boolean; data: unknown }>(
        `${API}/agent/team/status`,
      );
      setData(response.data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法获取智能体团队状态");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) return <Spin size="large" tip="正在读取智能体实时状态" style={{ display: "block", margin: "60px auto" }} />;
  if (error) return <Alert type="error" showIcon message="智能体团队状态获取失败" description={error}
    action={<Button onClick={loadData}>重试</Button>} />;
  if (!data) return <Alert type="warning" showIcon message="暂无 Agent 数据" />;

  const agents = data.agents || {};
  const recentExecutions = Object.entries(agents)
    .filter(([, info]: [string, any]) => info.last_task && info.last_execution_ms > 0)
    .map(([name, info]: [string, any]) => ({
      color: info.status === "running" ? "orange" : "green",
      children: (
        <>
          <Tag color={info.status === "running" ? "orange" : "blue"}>{name}</Tag>
          {info.last_task}（{(info.last_execution_ms / 1000).toFixed(1)}s）
        </>
      ),
    }));

  return (
    <div>
      <PageHeader
        title="园区智能体团队"
        description="查看各业务智能体的在线状态、专业能力与最近任务"
        backLabel="返回园区运营总览"
        extra={
          <Tag color="green" style={{ fontSize: 14, padding: "4px 12px" }}>
            全部 Agent 在线 · 今日已完成 {data.total_tasks_today} 个任务
          </Tag>
        }
      />

      {/* Agent Cards */}
      <Row gutter={[16, 16]}>
        {Object.entries(agents).map(([name, info]: [string, any]) => {
          const action = AGENT_ACTIONS[name];
          return (
          <Col xs={24} md={12} xl={8} key={name}>
            <Card
              hoverable
              className={action ? "interactive-card" : undefined}
              role={action ? "link" : undefined}
              tabIndex={action ? 0 : undefined}
              style={{
                borderTop: `3px solid ${STATUS_COLOR[info.status] || "#1677ff"}`,
                cursor: action ? "pointer" : "default",
                transition: "box-shadow 0.2s, transform 0.2s",
              }}
              onClick={() => { if (action) router.push(action.path); }}
              onKeyDown={(event) => {
                if (action && (event.key === "Enter" || event.key === " ")) {
                  event.preventDefault();
                  router.push(action.path);
                }
              }}
              title={action?.tip || ""}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                {ICON_MAP[info.icon] || <TeamOutlined />}
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{info.display}</div>
                  <div style={{ fontSize: 12, color: "#999" }}>{name}</div>
                </div>
                <Tag color={info.status === "running" ? "orange" : "blue"} style={{ marginLeft: "auto" }}>
                  {info.status === "running" ? "运行中" : "待命"}
                </Tag>
              </div>
              <div style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>
                最近任务: {info.last_task || "暂无"}
              </div>
              <Row gutter={8}>
                <Col span={8}>
                  <Statistic title="耗时" value={info.last_execution_ms > 0 ? `${(info.last_execution_ms / 1000).toFixed(1)}s` : "—"} valueStyle={{ fontSize: 14 }} />
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
              {action && (
                <div style={{ marginTop: 8, fontSize: 11, color: "#1677ff", textAlign: "center" }}>
                  <NodeIndexOutlined /> {action.label}
                </div>
              )}
            </Card>
          </Col>
        )})}
      </Row>

      {/* Execution Timeline */}
      <Card title="Agent 协作时间线" style={{ marginTop: 24 }}>
        {recentExecutions.length > 0
          ? <Timeline items={recentExecutions} />
          : <Alert type="info" showIcon message="暂无真实执行记录" description="完成一次 Agent 任务后，此处将展示后端返回的实际耗时。" />}
      </Card>
    </div>
  );
}
