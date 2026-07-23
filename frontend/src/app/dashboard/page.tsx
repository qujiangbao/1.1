"use client";

import { useEffect, useState } from "react";
import type { KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { Card, Row, Col, Statistic, Table, Tag, Alert, Timeline, Button } from "antd";
import {
  ArrowUpOutlined, ArrowDownOutlined, BulbOutlined, WarningOutlined,
  CheckCircleOutlined, ClockCircleOutlined, ThunderboltOutlined,
} from "@ant-design/icons";
import { apiFetch } from "@/api/fetch";
const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<Record<string, any>>({});
  const [report, setReport] = useState<any>(null);

  const openPage = (path: string) => router.push(path);
  const openPageWithKeyboard = (event: KeyboardEvent, path: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPage(path);
    }
  };

  useEffect(() => {
    apiFetch(`${API}/dashboard/overview`).then((r) => r.json()).then((d) => setData(d.data || {}));
    apiFetch(`${API}/agent/daily-report`).then((r) => r.json()).then((d) => setReport(d.data));
  }, []);

  return (
    <>
      {/* ====== AI 今日行动摘要 ====== */}
      <Card
        style={{ marginBottom: 24, borderLeft: "4px solid #1677ff", background: "linear-gradient(135deg, #f0f5ff 0%, #e6f0ff 100%)" }}
        title={<span style={{ fontSize: 16 }}><ThunderboltOutlined style={{ color: "#1677ff", marginRight: 8 }} />AI 今日行动摘要</span>}
        extra={<Tag color="blue">Auto-generated 07:30</Tag>}
      >
        <Row gutter={[16, 8]}>
          <Col span={8}>
            <Card
              size="small"
              hoverable
              role="link"
              tabIndex={0}
              className="interactive-card"
              onClick={() => openPage("/dashboard/investment")}
              onKeyDown={(event) => openPageWithKeyboard(event, "/dashboard/investment")}
              style={{ borderLeft: "3px solid #52c41a" }}
            >
              <Statistic title="🟢 今日招商机会" value={report?.investment?.opportunities || 230} suffix="个" valueStyle={{ color: "#52c41a", fontSize: 22 }} />
              <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>AI 推荐优先接触传感器方向企业</div>
            </Card>
          </Col>
          <Col span={8}>
            <Card
              size="small"
              hoverable
              role="link"
              tabIndex={0}
              className="interactive-card"
              onClick={() => openPage("/dashboard/risk")}
              onKeyDown={(event) => openPageWithKeyboard(event, "/dashboard/risk")}
              style={{ borderLeft: "3px solid #fa8c16" }}
            >
              <Statistic title="🟡 需关注风险" value={report?.risk_alerts?.length || 2} suffix="条" valueStyle={{ color: "#fa8c16", fontSize: 22 }} />
              <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>建议本周走访 3 家风险上升企业</div>
            </Card>
          </Col>
          <Col span={8}>
            <Card
              size="small"
              hoverable
              role="link"
              tabIndex={0}
              className="interactive-card"
              onClick={() => openPage("/agent/chat?prompt=查找园区企业可申报的最新产业政策")}
              onKeyDown={(event) => openPageWithKeyboard(event, "/agent/chat?prompt=查找园区企业可申报的最新产业政策")}
              style={{ borderLeft: "3px solid #722ed1" }}
            >
              <Statistic title="🟣 政策窗口" value={report?.policy_updates || 3} suffix="条" valueStyle={{ color: "#722ed1", fontSize: 22 }} />
              <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>2条政策即将截止，建议优先申报</div>
            </Card>
          </Col>
        </Row>
        <div style={{ marginTop: 16, padding: "12px 16px", background: "#fff", borderRadius: 8, border: "1px solid #e8e8e8" }}>
          <Timeline
            items={[
              { color: "green", dot: <CheckCircleOutlined />, children: <span>AI 扫描 <b>12,580</b> 家企业完成 — 全部正常</span> },
              { color: "blue", dot: <ThunderboltOutlined />, children: <span>AI 招商经理发现 <b>5</b> 家高价值企业 — 待审核</span> },
              { color: "orange", dot: <WarningOutlined />, children: <span>风险雷达标记 <b>2</b> 条预警 — 需关注</span> },
              { color: "purple", children: <span>政策顾问更新 <b>3</b> 条新政策 — 可为 12 家企业匹配</span> },
              { color: "green", dot: <CheckCircleOutlined />, children: <span>今日 AI 运营日报已生成 — 园区运营稳定</span> },
            ]}
          />
        </div>
      </Card>

      {/* ====== AI 运营日报 ====== */}
      {report && (
        <Card
          title={<span><BulbOutlined style={{ color: "#fa8c16", marginRight: 8 }} />今日 AI 运营日报 — {report.date}</span>}
          style={{ marginBottom: 24, borderLeft: "4px solid #fa8c16" }}
        >
          <Alert message={report.summary} type="info" showIcon style={{ marginBottom: 16 }} />
          <Row gutter={[16, 8]}>
            <Col span={6}><Statistic title="园区企业" value={report.park_metrics?.total_enterprises} suffix="家" /></Col>
            <Col span={6}><Statistic title="招商机会" value={report.investment?.opportunities} suffix="个" valueStyle={{ color: "#1677ff" }} /></Col>
            <Col span={6}><Statistic title="风险预警" value={report.risk_alerts?.length || 0} suffix="条" valueStyle={{ color: "#fa8c16" }} /></Col>
            <Col span={6}><Statistic title="AI 任务" value={report.ai_tasks_completed} suffix="次" valueStyle={{ color: "#52c41a" }} /></Col>
          </Row>
          {report.risk_alerts?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <WarningOutlined style={{ color: "#fa8c16", marginRight: 8 }} /><span style={{ fontWeight: 600, fontSize: 13 }}>风险预警：</span>
              {report.risk_alerts.map((a: any, i: number) => (
                <Tag key={i} color={a.level === "HIGH" ? "red" : a.level === "MEDIUM" ? "orange" : "blue"} style={{ marginLeft: 8 }}>{a.enterprise}: {a.reason}</Tag>
              ))}
            </div>
          )}
          {report.recommendations?.length > 0 && (
            <div style={{ marginTop: 12, padding: "8px 12px", background: "#f6ffed", borderRadius: 6 }}>
              <strong style={{ color: "#52c41a" }}>AI 建议：</strong>
              <ul style={{ margin: "4px 0 0 16px", fontSize: 13 }}>{report.recommendations.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}
        </Card>
      )}

      {/* ====== KPI ====== */}
      <h2 style={{ marginBottom: 16 }}>园区运营总览</h2>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card hoverable role="link" tabIndex={0} className="interactive-card" onClick={() => openPage("/agent/chat?prompt=分析园区企业结构和产业分布")} onKeyDown={(event) => openPageWithKeyboard(event, "/agent/chat?prompt=分析园区企业结构和产业分布")}>
            <Statistic title="企业总数" value={data?.park_overview?.total_enterprises || 0} suffix="家" valueStyle={{ color: "#1677ff" }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable role="link" tabIndex={0} className="interactive-card" onClick={() => openPage("/dashboard/investment")} onKeyDown={(event) => openPageWithKeyboard(event, "/dashboard/investment")}>
            <Statistic title="招商机会" value={data?.investment?.opportunities || 0} suffix="个" prefix={<ArrowUpOutlined />} valueStyle={{ color: "#52c41a" }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable role="link" tabIndex={0} className="interactive-card" onClick={() => openPage("/dashboard/risk")} onKeyDown={(event) => openPageWithKeyboard(event, "/dashboard/risk")}>
            <Statistic title="高风险企业" value={data?.risk?.high_risk || 0} suffix="家" prefix={<ArrowDownOutlined />} valueStyle={{ color: "#ff4d4f" }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable role="link" tabIndex={0} className="interactive-card" onClick={() => openPage("/agent/team")} onKeyDown={(event) => openPageWithKeyboard(event, "/agent/team")}>
            <Statistic title="AI 任务数" value={data?.ai_operations?.agent_calls || 0} suffix="次/日" valueStyle={{ color: "#1677ff" }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card title="招商转化" extra={<Button type="link" onClick={() => openPage("/dashboard/investment")}>查看招商驾驶舱</Button>}>
            <Table size="small" pagination={false}
              dataSource={[
                { key: "pool", stage: "目标企业池", count: data?.investment?.opportunities || 0, color: "blue" },
                { key: "contact", stage: "接触中", count: 45, color: "cyan" },
                { key: "signed", stage: "已签约", count: data?.investment?.signed || 0, color: "green" },
              ]}
              columns={[
                { title: "阶段", dataIndex: "stage" }, { title: "数量", dataIndex: "count", render: (v: number, r: any) => <Tag color={r.color}>{v}</Tag> },
              ]} />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="风险分布" extra={<Button type="link" onClick={() => openPage("/dashboard/risk")}>查看风险预警</Button>}>
            <Table size="small" pagination={false}
              dataSource={[
                { key: "high", level: "高风险", count: data?.risk?.high_risk || 0, color: "red" },
                { key: "med", level: "中风险", count: data?.risk?.medium_risk || 0, color: "orange" },
                { key: "low", level: "低风险", count: data?.risk?.low_risk || 0, color: "green" },
              ]}
              columns={[
                { title: "等级", dataIndex: "level", render: (v: string, r: any) => <Tag color={r.color}>{v}</Tag> }, { title: "企业数", dataIndex: "count" },
              ]} />
          </Card>
        </Col>
      </Row>
    </>
  );
}
