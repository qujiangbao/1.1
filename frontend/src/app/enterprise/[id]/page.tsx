"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Alert, Button, Card, Col, Descriptions, Empty, Row, Spin, Statistic, Tag } from "antd";
import {
  BankOutlined,
  FileProtectOutlined,
  SafetyCertificateOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { apiJson } from "@/api/fetch";
import PageHeader from "@/components/layout/PageHeader";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export default function EnterprisePage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [returnTo, setReturnTo] = useState("/dashboard/investment");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const requestedReturnTo = new URLSearchParams(window.location.search).get("returnTo");
    if (requestedReturnTo === "/dashboard/risk" || requestedReturnTo === "/dashboard/investment") {
      setReturnTo(requestedReturnTo);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    apiJson<{ success: boolean; data: any }>(
      `${API}/investment/profile/${encodeURIComponent(id)}`,
    )
      .then((payload) => setProfile(payload.data))
      .catch((caught) => {
        setProfile(null);
        setError(caught instanceof Error ? caught.message : "企业信息加载失败");
      })
      .finally(() => setLoading(false));
  }, [id, reloadKey]);

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
        {error ? (
          <Alert
            type="error"
            showIcon
            message="企业信息加载失败"
            description={error}
            action={<Button icon={<ReloadOutlined />} onClick={() => setReloadKey((value) => value + 1)}>重试</Button>}
          />
        ) : (
          <Empty description="未找到企业信息" />
        )}
      </div>
    );
  }

  const quality = profile.data_quality || {};
  const evidence = Array.isArray(profile.evidence) ? profile.evidence : [];

  return (
    <div>
      <PageHeader
        title={profile.name || `企业 #${id}`}
        description="展示快照中已采集的企业事实；未采集字段保持未知，不生成招商、风险或技术评分"
        backTo={returnTo}
      />

      <Alert
        type="info"
        showIcon
        message="当前画像不包含综合投资评分"
        description="专利、风险、融资和扩产意愿等数据尚不完整，系统不会用默认值代替。"
        style={{ marginBottom: 16 }}
      />

      <Row gutter={[16, 16]}>
        <Col xs={12} xl={6}>
          <Card>
            <Statistic
              title="注册资本"
              value={profile.registered_capital || "未知"}
              prefix={<BankOutlined />}
              valueStyle={{ color: "#1677ff", fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={12} xl={6}>
          <Card>
            <Statistic
              title="专利数量"
              value={profile.patents_count == null ? "未采集" : profile.patents_count}
              suffix={profile.patents_count == null ? undefined : "项"}
              prefix={<FileProtectOutlined />}
              valueStyle={{ fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={12} xl={6}>
          <Card>
            <Statistic
              title="企业身份"
              value={quality.identity_key === "credit_code" ? "信用代码" : "名称兜底"}
              prefix={<SafetyCertificateOutlined />}
              valueStyle={{ color: quality.identity_key === "credit_code" ? "#52c41a" : "#fa8c16", fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={12} xl={6}>
          <Card>
            <Statistic
              title="行业分类可信度"
              value={Math.round((profile.confidence_score ?? 0) * 100)}
              suffix="%"
              valueStyle={{ fontSize: 20 }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="企业基本信息" style={{ marginTop: 16 }}>
        <Descriptions column={{ xs: 1, md: 2 }} size="small">
          <Descriptions.Item label="统一信用代码">{profile.credit_code || "未采集"}</Descriptions.Item>
          <Descriptions.Item label="登记状态">{profile.enterprise_status || "未采集"}</Descriptions.Item>
          <Descriptions.Item label="法定代表人">{profile.legal_representative || "未采集"}</Descriptions.Item>
          <Descriptions.Item label="成立日期">{profile.established_date || "未采集"}</Descriptions.Item>
          <Descriptions.Item label="行业">{profile.industry || "未分类"}</Descriptions.Item>
          <Descriptions.Item label="企业类型">{profile.company_type || "未采集"}</Descriptions.Item>
          <Descriptions.Item label="地区">{profile.location || "未采集"}</Descriptions.Item>
          <Descriptions.Item label="注册资本数值">
            {profile.capital_amount == null
              ? "未采集"
              : `${profile.capital_amount} ${profile.capital_currency || ""}`.trim()}
          </Descriptions.Item>
          <Descriptions.Item label="注册地址" span={2}>{profile.address || "未采集"}</Descriptions.Item>
          <Descriptions.Item label="经营范围" span={2}>{profile.business_scope || "未采集"}</Descriptions.Item>
          <Descriptions.Item label="标签" span={2}>
            {profile.tags?.length
              ? profile.tags.map((tag: string) => <Tag key={tag}>{tag}</Tag>)
              : "无"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="数据质量与来源" style={{ marginTop: 16 }}>
        <Descriptions column={{ xs: 1, md: 2 }} size="small">
          <Descriptions.Item label="数据源">{profile.data_source}</Descriptions.Item>
          <Descriptions.Item label="快照时间">{profile.source_time || "未记录"}</Descriptions.Item>
          <Descriptions.Item label="信用代码">
            {quality.credit_code === "available" ? <Tag color="green">已采集</Tag> : <Tag>缺失</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="专利数据">
            {quality.patent_count === "available" ? <Tag color="green">已采集</Tag> : <Tag>未采集</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="注册资本">
            {quality.capital_amount === "available" ? <Tag color="green">已采集</Tag> : <Tag>缺失</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="证据记录">{evidence.length} 条</Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}
