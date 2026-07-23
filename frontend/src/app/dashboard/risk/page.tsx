"use client";

import { useState } from "react";
import type { KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, Statistic, Row, Col, Table, Tag, Progress } from "antd";
import {
  AlertOutlined, WarningOutlined, RiseOutlined, FallOutlined,
  CheckCircleOutlined, ExclamationCircleOutlined, RobotOutlined,
} from "@ant-design/icons";
import PageHeader from "@/components/layout/PageHeader";

const riskEnterprises = [
  { key: "1", enterprise_id: "risk-001", name: "某智能装备公司", score: 78, level: "HIGH", reason: "融资6个月未更新，疑似资金链紧张", trend: "up", action: "建议本周走访" },
  { key: "2", enterprise_id: "risk-002", name: "某机器人科技", score: 65, level: "MEDIUM", reason: "招聘量下降20%，核心人员流动", trend: "up", action: "关注人员变动" },
  { key: "3", enterprise_id: "risk-003", name: "某新能源材料", score: 62, level: "MEDIUM", reason: "供应商变更频繁，供应链风险", trend: "stable", action: "排查供应链" },
  { key: "4", enterprise_id: "risk-004", name: "某电子制造", score: 55, level: "MEDIUM", reason: "工商变更频繁，股权结构变动", trend: "up", action: "了解变更原因" },
  { key: "5", enterprise_id: "risk-005", name: "某AI科技", score: 48, level: "MEDIUM", reason: "银行贷款逾期30天", trend: "up", action: "评估偿债能力" },
  { key: "6", enterprise_id: "risk-006", name: "某芯片设计", score: 35, level: "LOW", reason: "季度营收同比下降15%", trend: "down", action: "正常关注" },
  { key: "7", enterprise_id: "risk-007", name: "某医疗器械", score: 32, level: "LOW", reason: "专利纠纷未解决", trend: "stable", action: "持续观察" },
  { key: "8", enterprise_id: "risk-008", name: "某数据服务", score: 28, level: "LOW", reason: "客户集中度偏高", trend: "stable", action: "正常关注" },
];

const levelColor: Record<string, string> = { HIGH: "#ff4d4f", MEDIUM: "#fa8c16", LOW: "#1890ff" };
const levelTag: Record<string, string> = { HIGH: "高风险", MEDIUM: "中风险", LOW: "低风险" };

export default function RiskDashboard() {
  const router = useRouter();
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const filteredEnterprises = selectedLevel
    ? riskEnterprises.filter((enterprise) => enterprise.level === selectedLevel)
    : riskEnterprises;

  const selectLevelWithKeyboard = (event: KeyboardEvent, level: string | null) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setSelectedLevel(level);
    }
  };

  return (
    <div>
      <PageHeader
        title={<><AlertOutlined style={{ color: "#ff4d4f", marginRight: 8 }} />风险驾驶舱</>}
        description="点击风险等级筛选企业，进入企业详情后可原路返回"
        backLabel="返回园区总览"
        extra={
          <Button
            type="primary"
            icon={<RobotOutlined />}
            onClick={() => router.push(`/agent/chat?prompt=${encodeURIComponent("分析园区高风险企业并给出处置建议")}`)}
          >
            AI 深度分析
          </Button>
        }
      />

      {/* KPI Row */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card hoverable role="button" tabIndex={0} className="interactive-card" onClick={() => setSelectedLevel("HIGH")} onKeyDown={(event) => selectLevelWithKeyboard(event, "HIGH")} style={{ borderColor: selectedLevel === "HIGH" ? "#ff4d4f" : undefined }}>
            <Statistic title="高风险企业" value={20} valueStyle={{ color: "#ff4d4f" }} prefix={<ExclamationCircleOutlined />} suffix={<RiseOutlined style={{ fontSize: 14, color: "#ff4d4f" }} />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable role="button" tabIndex={0} className="interactive-card" onClick={() => setSelectedLevel("MEDIUM")} onKeyDown={(event) => selectLevelWithKeyboard(event, "MEDIUM")} style={{ borderColor: selectedLevel === "MEDIUM" ? "#fa8c16" : undefined }}>
            <Statistic title="中风险企业" value={80} valueStyle={{ color: "#fa8c16" }} prefix={<WarningOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable role="button" tabIndex={0} className="interactive-card" onClick={() => setSelectedLevel("LOW")} onKeyDown={(event) => selectLevelWithKeyboard(event, "LOW")} style={{ borderColor: selectedLevel === "LOW" ? "#52c41a" : undefined }}>
            <Statistic title="低风险企业" value={500} valueStyle={{ color: "#52c41a" }} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable role="button" tabIndex={0} className="interactive-card" onClick={() => setSelectedLevel(null)} onKeyDown={(event) => selectLevelWithKeyboard(event, null)} style={{ borderColor: selectedLevel === null ? "#1677ff" : undefined }}>
            <Statistic title="AI 风险扫描 · 查看全部" value="12,580" suffix="家" valueStyle={{ color: "#1677ff" }} />
          </Card>
        </Col>
      </Row>

      {/* Risk Trend */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card title="风险等级分布" size="small">
            <div style={{ padding: "8px 0" }}>
              <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <Tag color="red">高风险</Tag><Progress percent={Math.round(20/600*100)} size="small" style={{ flex: 1, margin: 0 }} strokeColor="#ff4d4f" /><span style={{ fontSize: 12, color: "#999" }}>20</span>
              </div>
              <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <Tag color="orange">中风险</Tag><Progress percent={Math.round(80/600*100)} size="small" style={{ flex: 1, margin: 0 }} strokeColor="#fa8c16" /><span style={{ fontSize: 12, color: "#999" }}>80</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Tag color="blue">低风险</Tag><Progress percent={Math.round(500/600*100)} size="small" style={{ flex: 1, margin: 0 }} strokeColor="#1890ff" /><span style={{ fontSize: 12, color: "#999" }}>500</span>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="AI 风险洞察" size="small" style={{ borderLeft: "4px solid #fa8c16" }}>
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: 13 }}>
              <li style={{ marginBottom: 6 }}>近 30 天<span style={{ color: "#ff4d4f", fontWeight: 600 }}> 3 家</span>企业风险等级上调</li>
              <li style={{ marginBottom: 6 }}>机器人产业整体风险<span style={{ color: "#52c41a", fontWeight: 600 }}>低于园区平均</span></li>
              <li style={{ marginBottom: 6 }}><span style={{ color: "#fa8c16", fontWeight: 600 }}>融资动态</span>是最常见的风险触发因素</li>
              <li>AI 建议<span style={{ color: "#1677ff", fontWeight: 600 }}>每周扫描</span>一次高风险企业</li>
            </ul>
          </Card>
        </Col>
      </Row>

      {/* TOP Risk List */}
      <Card
        title={<><ExclamationCircleOutlined style={{ color: "#ff4d4f", marginRight: 8 }} />风险企业 TOP 8 · AI 实时监控</>}
        extra={<><Tag color={selectedLevel ? "blue" : "default"}>{selectedLevel ? `已筛选：${levelTag[selectedLevel]}` : "全部等级"}</Tag><Tag color="green">数据更新: 今日 07:30</Tag></>}
      >
        <Table
          dataSource={filteredEnterprises}
          size="small"
          pagination={false}
          columns={[
            { title: "排名", dataIndex: "key", key: "key", width: 50, render: (v: string) => <span style={{ fontWeight: 700, color: parseInt(v) <= 3 ? "#ff4d4f" : "#999" }}>#{v}</span> },
            { title: "企业名称", dataIndex: "name", key: "name", render: (v: string, record) => <Button type="link" style={{ padding: 0, fontWeight: 500 }} onClick={() => router.push(`/enterprise/${record.enterprise_id}?returnTo=${encodeURIComponent("/dashboard/risk")}`)}>{v}</Button> },
            { title: "风险评分", dataIndex: "score", key: "score", width: 100, render: (v: number) => <Progress percent={v} size="small" strokeColor={v >= 70 ? "#ff4d4f" : v >= 50 ? "#fa8c16" : "#52c41a"} /> },
            { title: "等级", dataIndex: "level", key: "level", width: 90, render: (v: string) => <Tag color={v === "HIGH" ? "red" : v === "MEDIUM" ? "orange" : "blue"}>{levelTag[v]}</Tag> },
            { title: "风险原因", dataIndex: "reason", key: "reason", ellipsis: true },
            { title: "趋势", dataIndex: "trend", key: "trend", width: 70, render: (v: string) => v === "up" ? <RiseOutlined style={{ color: "#ff4d4f" }} /> : v === "down" ? <FallOutlined style={{ color: "#52c41a" }} /> : <span style={{ color: "#999" }}>→</span> },
            { title: "建议行动", dataIndex: "action", key: "action", width: 130, render: (v: string) => <Tag color="blue">{v}</Tag> },
            { title: "操作", key: "operation", width: 90, render: (_, record) => <Button size="small" onClick={() => router.push(`/enterprise/${record.enterprise_id}?returnTo=${encodeURIComponent("/dashboard/risk")}`)}>查看详情</Button> },
          ]}
        />
      </Card>
    </div>
  );
}
