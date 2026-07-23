"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert, Card, Statistic, Tag, Row, Col, List, Descriptions, Spin, Input, Button, Empty,
} from "antd";
import {
  ArrowUpOutlined, SearchOutlined, TrophyOutlined, EnvironmentOutlined,
  BankOutlined, BulbOutlined, EyeOutlined,
} from "@ant-design/icons";
import { apiFetch } from "@/api/fetch";
import PageHeader from "@/components/layout/PageHeader";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface Enterprise {
  name: string;
  industry: string;
  score: number;
  location: string;
  registered_capital: string;
  match_reason: string;
  action: string;
  enterprise_id?: string;
}

export default function InvestmentDashboard() {
  const router = useRouter();
  const [enterprises, setEnterprises] = useState<Enterprise[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("机器人");
  const [error, setError] = useState("");

  const searchEnterprises = async (kw?: string) => {
    const q = kw || keyword;
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`${API}/investment/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ industry: q, limit: 10 }),
      });
      const data = await res.json();
      if (data.success) {
        setEnterprises(data.data?.enterprises || []);
      } else {
        setError(data.message || "企业搜索失败，请稍后重试");
      }
    } catch {
      setError("无法连接招商服务，请检查后端服务后重试");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    searchEnterprises();
  }, []);

  const scoreColor = (s: number) => (s >= 90 ? "#f50" : s >= 80 ? "#fa8c16" : s >= 70 ? "#1677ff" : "#999");
  const scoreLabel = (s: number) => (s >= 90 ? "强烈推荐" : s >= 80 ? "推荐" : s >= 70 ? "关注" : "备选");
  const actionColor = (a: string) =>
    a.includes("优先") ? "red" : a.includes("积极") ? "orange" : a.includes("关注") ? "blue" : "default";

  return (
    <div>
      <PageHeader
        title="招商驾驶舱"
        description="搜索目标产业企业，查看推荐理由并进入企业画像"
        backLabel="返回园区总览"
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="目标企业池" value={230} prefix={<ArrowUpOutlined />} valueStyle={{ color: "#1677ff" }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="AI 推荐" value={enterprises.length || 5} suffix="家" valueStyle={{ color: "#52c41a" }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已签约" value={12} valueStyle={{ color: "#52c41a" }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="转化率" value={5.2} suffix="%" valueStyle={{ color: "#1677ff" }} /></Card>
        </Col>
      </Row>

      {/* Search bar */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={12} align="middle">
          <Col flex="auto">
            <Input
              size="large"
              placeholder="搜索产业方向，如：机器人、新能源、半导体..."
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onPressEnter={() => searchEnterprises()}
              prefix={<SearchOutlined />}
            />
          </Col>
          <Col>
            <Button type="primary" size="large" icon={<SearchOutlined />} onClick={() => searchEnterprises()} loading={loading}>
              搜索
            </Button>
          </Col>
        </Row>
      </Card>

      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          action={<Button size="small" onClick={() => searchEnterprises()}>重新加载</Button>}
          style={{ marginBottom: 16 }}
        />
      )}

      <h3 style={{ marginBottom: 12 }}>
        <TrophyOutlined style={{ color: "#fa8c16", marginRight: 8 }} />
        AI 智能推荐 · 招商目标企业 Top 5
      </h3>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16, color: "#999" }}>AI招商经理正在搜索和分析企业...</p>
        </div>
      ) : enterprises.length === 0 ? (
        <Empty description="未找到匹配企业，请尝试其他关键词" />
      ) : (
        <List
          dataSource={enterprises.slice(0, 5)}
          renderItem={(item, idx) => (
            <Card
              key={idx}
              size="small"
              hoverable
              style={{ marginBottom: 12 }}
              title={
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: idx === 0 ? "#ffd700" : idx === 1 ? "#c0c0c0" : idx === 2 ? "#cd7f32" : "#f0f0f0",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 700,
                      fontSize: 14,
                      color: idx < 3 ? "#fff" : "#666",
                    }}
                  >
                    {idx + 1}
                  </span>
                  <span style={{ fontSize: 15, fontWeight: 600 }}>{item.name}</span>
                  <Tag
                    color={scoreColor(item.score)}
                    style={{ fontWeight: 600 }}
                  >
                    {item.score} 分 · {scoreLabel(item.score)}
                  </Tag>
                  <Tag color={actionColor(item.action)}>{item.action}</Tag>
                </div>
              }
            >
              <Row gutter={[16, 8]}>
                <Col span={8}>
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label={<><BankOutlined /> 行业</>}>
                      <Tag color="blue">{item.industry}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label={<><EnvironmentOutlined /> 所在地</>}>
                      {item.location}
                    </Descriptions.Item>
                    <Descriptions.Item label="注册资本">
                      {item.registered_capital}
                    </Descriptions.Item>
                  </Descriptions>
                </Col>
                <Col span={8}>
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="技术实力">
                      <Tag color="blue">行业领先</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="扩产意愿">
                      <Tag color="green">高</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="经营状况">
                      <Tag color="green">良好</Tag>
                    </Descriptions.Item>
                  </Descriptions>
                </Col>
                <Col span={8}>
                  <Card
                    size="small"
                    style={{ background: "#fffbe6", border: "1px solid #ffe58f" }}
                    title={<span style={{ fontSize: 12 }}><BulbOutlined style={{ color: "#fa8c16" }} /> 匹配理由</span>}
                  >
                    <p style={{ margin: 0, fontSize: 13, color: "#595959" }}>{item.match_reason}</p>
                  </Card>
                  <div style={{ marginTop: 8, fontSize: 11, color: "#999" }}>
                    综合评分维度：产业匹配 30% · 成长性 25% · 技术 20% · 资本 15% · 人才 10%
                  </div>
                  <Button
                    type="primary"
                    ghost
                    size="small"
                    icon={<EyeOutlined />}
                    style={{ marginTop: 12 }}
                    onClick={() => router.push(`/enterprise/${encodeURIComponent(item.enterprise_id || item.name || String(idx + 1))}?returnTo=${encodeURIComponent("/dashboard/investment")}`)}
                  >
                    查看企业画像
                  </Button>
                </Col>
              </Row>
            </Card>
          )}
        />
      )}
    </div>
  );
}
