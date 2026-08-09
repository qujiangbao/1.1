"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Col, Empty, Progress, Row, Statistic, Tag } from "antd";
import {
  ArrowUpOutlined, ArrowDownOutlined, ThunderboltOutlined,
  BulbOutlined, WarningOutlined, RiseOutlined, BarChartOutlined, SyncOutlined,
} from "@ant-design/icons";
import { apiJson } from "@/api/fetch";
import { useDataMode } from "@/contexts/DataModeContext";
import PageHeader from "@/components/layout/PageHeader";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface BIData {
  kpi_cards: KpiCard[];
  industry_distribution: IndustryItem[];
  investment_funnel: FunnelItem[];
  risk_trend: RiskTrendItem[];
  ai_usage: AIUsageItem[];
  insights: Insights;
  metadata: {
    is_demo: boolean;
    disclaimer?: string | null;
    investment_funnel_data_available: boolean;
    risk_data_available?: boolean;
  };
}

interface KpiCard {
  key: string; title: string; value: number | null; unit: string;
  trend: string; trend_up: boolean; color: string;
}

interface IndustryItem {
  name: string; value: number; pct: number; color: string;
}

interface FunnelItem {
  stage: string; count: number; color: string;
}

interface RiskTrendItem {
  month: string; high: number; medium: number; low: number;
}

interface AIUsageItem {
  agent: string; calls: number; pct: number;
}

interface Insights {
  summary: string;
  opportunities: { area: string; action: string }[];
  alerts: { level: string; msg: string }[];
}

/* ===== Inline chart components (no external deps) ===== */

function BarChart({ data, maxVal }: { data: IndustryItem[]; maxVal: number }) {
  const [hoverName, setHoverName] = useState<string | null>(null);
  if (!data.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无企业产业分布数据" />;
  }
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 12, height: 220, paddingTop: 8 }}>
      {data.map((d) => {
        const active = hoverName === d.name;
        return (
        <div key={d.name} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end" }}>
          <span style={{ fontSize: 11, color: active ? "#1677ff" : "#666", marginBottom: 2, fontWeight: active ? 700 : 600 }}>
            {active ? `${d.value}家` : `${d.pct}%`}
          </span>
          <div
            onMouseEnter={() => setHoverName(d.name)}
            onMouseLeave={() => setHoverName(null)}
            style={{
              width: "100%", maxWidth: 60, cursor: "pointer",
              height: `${(d.value / maxVal) * 180}px`,
              background: active
                ? `linear-gradient(180deg, ${d.color}, ${d.color}88)`
                : `linear-gradient(180deg, ${d.color}cc, ${d.color}44)`,
              borderRadius: "6px 6px 0 0",
              transition: "height 0.6s ease, opacity 0.2s",
              position: "relative",
              opacity: hoverName && !active ? 0.5 : 1,
            }}>
            <span style={{
              position: "absolute", bottom: -22, left: "50%", transform: "translateX(-50%)",
              fontSize: 11, color: active ? "#1677ff" : "#999", whiteSpace: "nowrap",
              fontWeight: active ? 600 : 400,
            }}>
              {d.name}
            </span>
          </div>
        </div>
      )})}
    </div>
  );
}

function FunnelChart({ data }: { data: FunnelItem[] }) {
  if (!data.length || data.every((item) => item.count === 0)) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="招商漏斗业务表尚未接入"
      />
    );
  }
  const maxCount = data[0]?.count || 1;
  const barColors = ["#1677ff", "#52c41a", "#faad14", "#fa8c16", "#ff4d4f"];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "8px 0" }}>
      {data.map((d, i) => (
        <div key={d.stage} style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 80, fontSize: 12, fontWeight: 500, textAlign: "right", color: "#555" }}>
            {d.stage}
          </span>
          <div style={{
            flex: 1, height: 28,
            background: `linear-gradient(90deg, ${barColors[i]}dd, ${barColors[i]}44)`,
            borderRadius: 4,
            width: `${(d.count / maxCount) * 100}%`,
            display: "flex", alignItems: "center", paddingLeft: 10,
            transition: "width 0.6s ease",
          }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#fff", textShadow: "0 1px 2px rgba(0,0,0,0.2)" }}>
              {d.count}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function RiskTrendChart({ data }: { data: RiskTrendItem[] }) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  if (!data.length) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="暂无真实风险历史记录"
      />
    );
  }
  const svgW = 500, svgH = 200, pad = { top: 10, right: 20, bottom: 30, left: 35 };
  const w = svgW - pad.left - pad.right;
  const h = svgH - pad.top - pad.bottom;
  const maxY = 600;
  const colors: Record<string, string> = { high: "#ff4d4f", medium: "#faad14", low: "#52c41a" };
  const labels: Record<string, string> = { high: "高风险", medium: "中风险", low: "低风险" };

  const points = (key: "high" | "medium" | "low") =>
    data.map((d, i) => {
      const x = pad.left + (i / Math.max(data.length - 1, 1)) * w;
      const y = pad.top + h - (d[key] / maxY) * h;
      return `${x},${y}`;
    }).join(" ");

  const hoverData = hoverIdx !== null ? data[hoverIdx] : null;
  const hoverX = hoverIdx !== null ? pad.left + (hoverIdx / Math.max(data.length - 1, 1)) * w : 0;

  return (
    <div style={{ position: "relative" }}>
      {hoverData && (
        <div style={{
          position: "absolute", top: 4, left: hoverX,
          transform: "translateX(-50%)", background: "#333", color: "#fff", borderRadius: 6,
          padding: "6px 10px", fontSize: 12, zIndex: 10, whiteSpace: "nowrap",
          pointerEvents: "none",
        }}>
          <strong>{hoverData.month}</strong>
          <div style={{ marginTop: 2 }}>
            {(["high","medium","low"] as const).map((k) => (
              <span key={k} style={{ color: colors[k], marginRight: 8 }}>
                {labels[k]}: {hoverData[k]}家
              </span>
            ))}
          </div>
        </div>
      )}
      <svg viewBox={`0 0 ${svgW} ${svgH}`} style={{ width: "100%", height: 200 }}>
        {[0, 200, 400, 600].map((v) => {
          const y = pad.top + h - (v / maxY) * h;
          return <g key={v}>
            <line x1={pad.left} y1={y} x2={svgW - pad.right} y2={y} stroke="#f0f0f0" strokeWidth={1} />
            <text x={pad.left - 6} y={y + 4} textAnchor="end" fontSize={10} fill="#999">{v}</text>
          </g>;
        })}
        {(["low","medium","high"] as const).map((k) => (
          <polyline key={k} points={points(k)} fill="none" stroke={colors[k]} strokeWidth={2} />
        ))}
        {data.map((d, i) => {
          const x = pad.left + (i / Math.max(data.length - 1, 1)) * w;
          return (
            <g key={d.month}>
              <rect x={x - 12} y={pad.top} width={24} height={h}
                    fill="transparent" style={{ cursor: "pointer" }}
                    onMouseEnter={() => setHoverIdx(i)}
                    onMouseLeave={() => setHoverIdx(null)} />
              <text x={x} y={svgH - 8} textAnchor="middle" fontSize={10}
                    fill={hoverIdx === i ? "#1677ff" : "#999"} fontWeight={hoverIdx === i ? 600 : 400}>
                {d.month}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function AIUsageBreakdown({ data }: { data: AIUsageItem[] }) {
  if (!data.length) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="今日暂无 Agent 调用记录"
      />
    );
  }
  const colors = ["#1677ff", "#52c41a", "#faad14", "#722ed1", "#13c2c2", "#eb2f96"];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "8px 0" }}>
      {data.map((d, i) => (
        <div key={d.agent} style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 90, fontSize: 12, color: "#555", textAlign: "right", whiteSpace: "nowrap" }}>
            {d.agent}
          </span>
          <Progress
            percent={d.pct}
            showInfo={false}
            strokeColor={colors[i]}
            trailColor="#f0f0f0"
            style={{ flex: 1, margin: 0 }}
          />
          <span style={{ width: 60, fontSize: 12, fontWeight: 600, color: colors[i] }}>
            {d.calls}次
          </span>
        </div>
      ))}
    </div>
  );
}

/* ===== Main Page ===== */

export default function BIDashboardPage() {
  const { mode, isDemo } = useDataMode();
  const [data, setData] = useState<BIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await apiJson<{ success: boolean; data: BIData }>(
        `${API}/dashboard/bi?mode=${mode}`,
      );
      setData(response.data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  if (loading) {
    return (
      <Card loading style={{ minHeight: 600 }}>
        <div style={{ textAlign: "center", padding: 60, color: "#999" }}>
          <ThunderboltOutlined style={{ fontSize: 48, marginBottom: 16 }} />
          <div>AI 正在生成经营分析看板...</div>
        </div>
      </Card>
    );
  }

  if (!data) {
    return (
      <Alert
        type="error"
        message="数据加载失败"
        description={error}
        showIcon
        action={<Button onClick={loadData}>重试</Button>}
      />
    );
  }

  const maxIndustryVal = Math.max(
    1,
    ...data.industry_distribution.map((item) => item.value),
  );

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>
      <PageHeader
        title={<><BarChartOutlined style={{ color: "#1677ff", marginRight: 8 }} />经营分析看板</>}
        description="聚合园区经营指标、产业分布、招商漏斗与风险趋势。"
        backLabel="返回园区运营总览"
        extra={
          <Button icon={<SyncOutlined />} onClick={() => void loadData()}>
            刷新数据
          </Button>
        }
      />

      {/* ===== Row 1: KPI Cards ===== */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        {data.kpi_cards.map((card) => (
          <Col xs={24} sm={12} lg={6} key={card.key}>
            <Card
              hoverable
              style={{
                borderTop: `3px solid ${card.color}`,
                borderRadius: 8,
              }}
              styles={{ body: { padding: "16px 20px" } }}
            >
              <Statistic
                title={<span style={{ fontSize: 13, color: "#666" }}>{card.title}</span>}
                value={card.value ?? "待接入"}
                suffix={card.unit}
                valueStyle={{ color: card.color, fontSize: 28, fontWeight: 700 }}
              />
              <div style={{ marginTop: 8, fontSize: 13 }}>
                <span style={{ color: card.trend_up ? "#52c41a" : "#ff4d4f", fontWeight: 600 }}>
                  {card.trend_up ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {card.trend}
                </span>
                {isDemo && <span style={{ color: "#999", marginLeft: 4 }}>演示口径</span>}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* ===== Row 2: Industry + Funnel ===== */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={14}>
          <Card
            title={<span><RiseOutlined style={{ color: "#1677ff", marginRight: 8 }} />产业分布</span>}
            extra={<Tag color="blue">Top 6</Tag>}
          >
            <BarChart data={data.industry_distribution} maxVal={maxIndustryVal} />
            <div style={{ marginTop: 30, display: "flex", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
              {data.industry_distribution.map((d) => (
                <span key={d.name} style={{ fontSize: 11, color: "#666" }}>
                  <span style={{
                    display: "inline-block", width: 8, height: 8, borderRadius: 2,
                    background: d.color, marginRight: 4, verticalAlign: "middle",
                  }} />
                  {d.name} {d.pct}%
                </span>
              ))}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card
            title={<span><RiseOutlined style={{ color: "#52c41a", marginRight: 8 }} />招商转化漏斗</span>}
            extra={<span style={{ fontSize: 12, color: "#999" }}>本月</span>}
          >
            {data.metadata.investment_funnel_data_available ? (
              <FunnelChart data={data.investment_funnel} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="招商漏斗待接入" />
            )}
          </Card>
        </Col>
      </Row>

      {/* ===== Row 3: Risk Trend + AI Usage ===== */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={14}>
          <Card
            title={<span><WarningOutlined style={{ color: "#ff4d4f", marginRight: 8 }} />风险趋势（6个月）</span>}
            extra={
              <div style={{ display: "flex", gap: 12, fontSize: 12 }}>
                <span><span style={{ color: "#ff4d4f" }}>●</span> 高风险</span>
                <span><span style={{ color: "#faad14" }}>●</span> 中风险</span>
                <span><span style={{ color: "#52c41a" }}>●</span> 低风险</span>
              </div>
            }
          >
            {data.metadata.risk_data_available ? (
              <RiskTrendChart data={data.risk_trend} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="风险趋势尚未评估" />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card
            title={<span><ThunderboltOutlined style={{ color: "#722ed1", marginRight: 8 }} />AI Agent 调用分布</span>}
          >
            <AIUsageBreakdown data={data.ai_usage} />
          </Card>
        </Col>
      </Row>

      {/* ===== Row 4: AI Insights ===== */}
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card
            title={<span><BulbOutlined style={{ color: "#fa8c16", marginRight: 8 }} />AI 洞察与建议</span>}
            style={{ borderLeft: "4px solid #fa8c16" }}
          >
            <Alert message={data.insights.summary} type="info" showIcon style={{ marginBottom: 16 }} />

            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <h4 style={{ color: "#52c41a", marginBottom: 12 }}>
                  <RiseOutlined style={{ marginRight: 6 }} />发展机会
                </h4>
                {data.insights.opportunities.map((op, i) => (
                  <Card key={i} size="small" style={{ marginBottom: 8, background: "#f6ffed" }}>
                    <strong>{op.area}</strong>
                    <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>{op.action}</div>
                  </Card>
                ))}
              </Col>

              <Col xs={24} md={12}>
                <h4 style={{ color: "#fa8c16", marginBottom: 12 }}>
                  <WarningOutlined style={{ marginRight: 6 }} />预警提醒
                </h4>
                {data.insights.alerts.map((a, i) => (
                  <Alert
                    key={i}
                    message={a.msg}
                    type={a.level === "warning" ? "warning" : "info"}
                    showIcon
                    style={{ marginBottom: 8 }}
                  />
                ))}
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
