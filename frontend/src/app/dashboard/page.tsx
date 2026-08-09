"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, Button, Empty, Progress, Tag } from "antd";
import {
  AlertOutlined,
  ArrowRightOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  RobotOutlined,
  SearchOutlined,
  SyncOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { apiJson } from "@/api/fetch";
import { useDataMode } from "@/contexts/DataModeContext";
import PageHeader from "@/components/layout/PageHeader";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export default function DashboardPage() {
  const router = useRouter();
  const { mode, isDemo } = useDataMode();
  const [data, setData] = useState<Record<string, any>>({});
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [overview, dailyReport] = await Promise.all([
        apiJson<{ success: boolean; data: Record<string, any> }>(`${API}/dashboard/overview?mode=${mode}`),
        apiJson<{ success: boolean; data: any }>(`${API}/agent/daily-report?mode=${mode}`),
      ]);
      setData(overview.data || {});
      setReport(dailyReport.data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "园区数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => { void loadDashboard(); }, [loadDashboard]);

  const enterpriseCount = report?.park_metrics?.total_enterprises ?? data?.park_overview?.total_enterprises ?? 0;
  const policyCount = report?.policy_total ?? data?.policy?.total ?? 0;
  const riskCount = isDemo
    ? (report?.risk_alerts?.length ?? data?.risk?.high_risk ?? 0)
    : (report?.risk_alerts?.length || data?.risk?.high_risk || 0);
  const agentCalls = report?.ai_tasks_completed ?? data?.ai_operations?.agent_calls ?? 0;
  const dataLabel = isDemo ? "演示沙盘" : "公开快照";

  const metrics = [
    {
      label: isDemo ? "示例企业场景" : "企业公开快照",
      value: enterpriseCount,
      unit: "家",
      foot: "进入企业与招商决策",
      path: "/dashboard/investment",
      icon: <TeamOutlined />,
      color: "#2f6f64",
      soft: "#e7f0ed",
    },
    {
      label: "可检索政策正文",
      value: policyCount,
      unit: "条",
      foot: "查看申报条件与依据",
      path: "/management/policies",
      icon: <DatabaseOutlined />,
      color: "#58645f",
      soft: "#ecefeb",
    },
    {
      label: isDemo ? "风险演示事件" : "需关注风险",
      value: riskCount || (isDemo ? 0 : "待评估"),
      unit: riskCount ? "条" : "",
      foot: isDemo ? "查看风险发现闭环" : "进入风险证据核验",
      path: "/dashboard/risk",
      icon: <AlertOutlined />,
      color: "#c58a42",
      soft: "#f8efe3",
    },
    {
      label: "今日 AI 任务",
      value: agentCalls,
      unit: "次",
      foot: "查看智能体协作状态",
      path: "/agent/team",
      icon: <RobotOutlined />,
      color: "#4f8f7a",
      soft: "#e8f2ee",
    },
  ];

  const quickActions = [
    {
      title: "启动园区研判",
      description: "用一句需求调度产业、招商、风险与政策 Agent",
      value: "进入工作台",
      path: "/agent/workspace",
      icon: <ThunderboltOutlined />,
      color: "#2f6f64",
      soft: "#e7f0ed",
    },
    {
      title: "生成招商目标清单",
      description: "围绕产业链缺口筛选企业并查看评分依据",
      value: "招商决策",
      path: "/dashboard/investment",
      icon: <SearchOutlined />,
      color: "#4f8f7a",
      soft: "#e8f2ee",
    },
    {
      title: "核验企业风险",
      description: "查看风险等级、原因、证据与建议处置动作",
      value: riskCount ? `${riskCount} 条关注` : "开始核验",
      path: "/dashboard/risk",
      icon: <AlertOutlined />,
      color: "#c58a42",
      soft: "#f8efe3",
    },
    {
      title: "检索惠企政策",
      description: "从公开政策快照中匹配申报条件与支持方向",
      value: `${policyCount} 条政策`,
      path: "/management/policies",
      icon: <FileSearchOutlined />,
      color: "#58645f",
      soft: "#ecefeb",
    },
  ];

  return (
    <div>
      <PageHeader
        title="园区运营总览"
        description="把企业、招商、风险、政策和 AI 任务放进同一张运营地图。"
        backTo="/agent/workspace"
        backLabel="工作台"
        extra={
          <Button icon={<SyncOutlined spin={loading} />} loading={loading} onClick={() => void loadDashboard()}>
            更新态势
          </Button>
        }
      />

      {error && (
        <Alert
          type="error"
          showIcon
          message="园区数据加载失败"
          description={error}
          action={<Button onClick={() => void loadDashboard()}>重新加载</Button>}
          style={{ marginBottom: 18 }}
        />
      )}

      <section className="dashboard-hero" aria-label="园区今日态势">
        <div className="dashboard-hero-copy">
          <span className="dashboard-kicker">TODAY&apos;S PARK PULSE · {dataLabel}</span>
          <h1>今天，园区最值得关注什么？</h1>
          <p>
            {report?.summary || "汇总企业、招商、风险与政策状态，让管理者从异常和机会出发，而不是从报表开始。"}
          </p>
          <div className="dashboard-hero-actions">
            <Button type="primary" size="large" icon={<ThunderboltOutlined />} onClick={() => router.push("/agent/workspace")}>
              发起 AI 研判
            </Button>
            <Button size="large" icon={<BarChartOutlined />} onClick={() => router.push("/dashboard/bi")}>
              查看经营分析
            </Button>
          </div>
        </div>

        <div className="dashboard-hero-panel">
          <div className="hero-panel-head">
            <strong>运营状态</strong>
            <Tag color="success" icon={<CheckCircleOutlined />}>系统在线</Tag>
          </div>
          <div className="hero-panel-list">
            <div className="hero-panel-item"><i /><span>企业数据</span><b>{enterpriseCount} 家</b></div>
            <div className="hero-panel-item"><i style={{ background: "#8ba49c" }} /><span>政策知识库</span><b>{policyCount} 条</b></div>
            <div className="hero-panel-item"><i style={{ background: "#d3a15f" }} /><span>风险关注</span><b>{riskCount || (isDemo ? 0 : "待评估")}</b></div>
            <div className="hero-panel-item"><i style={{ background: "#5fa89a" }} /><span>AI 协作任务</span><b>{agentCalls} 次</b></div>
          </div>
        </div>
      </section>

      {!isDemo && report?.investment?.data_available === false && (
        <Alert
          type="info"
          showIcon
          message="招商漏斗和风险评估等待业务系统接入"
          description="当前只展示有公开来源的数据；缺失指标标记为待接入，不使用演示数字代替。"
          style={{ marginBottom: 18 }}
        />
      )}

      <section className="metric-grid" aria-label="核心运营指标">
        {metrics.map((metric) => (
          <button
            type="button"
            className="metric-card"
            key={metric.label}
            onClick={() => router.push(metric.path)}
            style={{ "--metric-color": metric.color, "--metric-soft": metric.soft } as React.CSSProperties}
          >
            <div className="metric-card-head">
              <span>{metric.label}</span>
              <span className="metric-icon">{metric.icon}</span>
            </div>
            <div className="metric-value"><strong>{metric.value}</strong><span>{metric.unit}</span></div>
            <div className="metric-foot">{metric.foot} <ArrowRightOutlined /></div>
          </button>
        ))}
      </section>

      <section className="dashboard-grid">
        <div className="dashboard-section-card">
          <div className="dashboard-section-head">
            <div><h2>下一步行动</h2><p>从运营问题直接进入决策流程</p></div>
            <Tag color={isDemo ? "orange" : "blue"}>{dataLabel}</Tag>
          </div>
          <div className="action-list">
            {quickActions.map((action) => (
              <button type="button" className="action-row" key={action.title} onClick={() => router.push(action.path)}>
                <span className="action-row-icon" style={{ "--action-color": action.color, "--action-soft": action.soft } as React.CSSProperties}>{action.icon}</span>
                <span className="action-row-copy"><strong>{action.title}</strong><span>{action.description}</span></span>
                <span className="action-row-value">{action.value} <ArrowRightOutlined /></span>
              </button>
            ))}
          </div>
        </div>

        <div className="dashboard-section-card">
          <div className="dashboard-section-head">
            <div><h2>AI 运营简报</h2><p>{report?.date || "今日"} · 自动汇总</p></div>
            <RobotOutlined style={{ color: "#2563eb", fontSize: 21 }} />
          </div>

          {report ? (
            <>
              <div style={{ marginBottom: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, color: "#53627a", fontSize: 12 }}>
                  <span>数据准备度</span><strong style={{ color: "#13213a" }}>{isDemo ? 100 : policyCount ? 72 : 38}%</strong>
                </div>
                <Progress percent={isDemo ? 100 : policyCount ? 72 : 38} showInfo={false} strokeColor={{ from: "#2563eb", to: "#06b6d4" }} />
              </div>

              {report.risk_alerts?.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message={`${report.risk_alerts.length} 条风险需要关注`}
                  description={report.risk_alerts.slice(0, 2).map((item: any) => item.enterprise).join("、")}
                  style={{ marginBottom: 14 }}
                />
              )}

              {report.recommendations?.length > 0 ? (
                <div className="recommendation-box">
                  <strong>今日建议</strong>
                  <ul>{report.recommendations.slice(0, 4).map((item: string, index: number) => <li key={index}>{item}</li>)}</ul>
                </div>
              ) : (
                <div className="recommendation-box"><strong>运行稳定</strong><div style={{ marginTop: 5 }}>暂无新的处置建议，可发起一次 AI 园区研判。</div></div>
              )}
            </>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={loading ? "正在生成运营简报" : "暂无运营简报"} />
          )}
        </div>
      </section>
    </div>
  );
}
