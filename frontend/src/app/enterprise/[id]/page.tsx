"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, Descriptions, Tag, Spin, Statistic, Row, Col, Progress, Empty } from "antd";
import { SafetyCertificateOutlined, RiseOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { apiFetch } from "@/api/fetch";
import PageHeader from "@/components/layout/PageHeader";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export default function EnterprisePage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [returnTo, setReturnTo] = useState("/dashboard/investment");

  useEffect(() => {
    const requestedReturnTo = new URLSearchParams(window.location.search).get("returnTo");
    if (requestedReturnTo === "/dashboard/risk" || requestedReturnTo === "/dashboard/investment") {
      setReturnTo(requestedReturnTo);
    }
  }, []);

  useEffect(() => {
    apiFetch(`${API}/investment/profile/${id}`)
      .then((r) => r.json())
      .then((d) => setProfile(d.data))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div>
        <PageHeader title="企业画像" backTo={returnTo} />
        <Spin style={{ display: "block", margin: "40px auto" }} />
      </div>
    );
  }
  if (!profile) {
    return (
      <div>
        <PageHeader title="企业画像" backTo={returnTo} />
        <Empty description="未找到企业信息" />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={profile.name || `企业 #${id}`}
        description="企业基本信息、技术能力、招商与风险综合评估"
        backTo={returnTo}
      />

      <Row gutter={[16, 16]}>
        <Col span={6}><Card><Statistic title="招商评分" value={profile.investment_score || 85} suffix="分" prefix={<RiseOutlined />} valueStyle={{ color: "#52c41a" }} /></Card></Col>
        <Col span={6}><Card><Statistic title="风险评分" value={profile.risk_score || 28} suffix="分" prefix={<SafetyCertificateOutlined />} valueStyle={{ color: "#1677ff" }} /></Card></Col>
        <Col span={6}><Card><Statistic title="技术评分" value={profile.technology?.tech_score || 88} suffix="分" prefix={<ThunderboltOutlined />} /></Card></Col>
        <Col span={6}><Card><Progress type="circle" percent={profile.investment_score || 85} size={80} format={(p) => `${p}分`} /></Card></Col>
      </Row>

      <Card title="基本信息" style={{ marginTop: 16 }}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="行业">{profile.industry || "—"}</Descriptions.Item>
          <Descriptions.Item label="地区">{profile.location || "—"}</Descriptions.Item>
          <Descriptions.Item label="融资阶段">{profile.finance?.funding_stage || "—"}</Descriptions.Item>
          <Descriptions.Item label="员工规模">{profile.employee_count || "—"}人</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="招商评估" style={{ marginTop: 16 }}>
        {profile.recommendation && (
          <Tag color="green" style={{ marginBottom: 12, fontSize: 14, padding: "4px 12px" }}>
            {profile.recommendation}
          </Tag>
        )}
        {profile.match_reasons?.map((r: string, i: number) => (
          <Tag key={i} style={{ marginBottom: 4 }}>{r}</Tag>
        ))}
      </Card>
    </div>
  );
}
