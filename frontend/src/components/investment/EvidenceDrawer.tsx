"use client";

import {
  Alert,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Grid,
  Progress,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  DatabaseOutlined,
  LinkOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import type { EvidenceItem } from "@/types/investment";
import styles from "@/components/investment/investment.module.css";

const { Link, Paragraph, Text, Title } = Typography;

const UNKNOWN_LABELS: Record<string, string> = {
  growth: "成长数据",
  landing_intent: "落地意愿",
  policy_fit: "政策申报条件",
  risk: "真实风险评估",
};

interface EvidenceDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  evidence: EvidenceItem[];
  unknownFields?: string[];
  warnings?: string[];
}

function displayValue(value: unknown) {
  if (value == null || value === "") return "未记录";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function EvidenceDrawer({
  open,
  onClose,
  title,
  evidence,
  unknownFields = [],
  warnings = [],
}: EvidenceDrawerProps) {
  const screens = Grid.useBreakpoint();
  const averageConfidence = evidence.length
    ? Math.round(
        (evidence.reduce((total, item) => total + item.confidence, 0) /
          evidence.length) *
          100,
      )
    : 0;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={screens.md ? 720 : "100%"}
      title={
        <Space>
          <SafetyCertificateOutlined style={{ color: "#1677ff" }} />
          <span>{title} · 证据链</span>
        </Space>
      }
    >
      <div className={styles.evidenceIntro}>
        <Space wrap size={[8, 8]}>
          <Tag color="blue">{evidence.length} 条证据</Tag>
          <Tag color={averageConfidence >= 70 ? "green" : "gold"}>
            平均置信度 {averageConfidence}%
          </Tag>
          <Tag color={unknownFields.length ? "orange" : "green"}>
            {unknownFields.length ? `${unknownFields.length} 项数据缺口` : "关键字段已覆盖"}
          </Tag>
        </Space>
        <Paragraph type="secondary" style={{ margin: "10px 0 0" }}>
          每条结论均关联采集工具、版本化快照和原始来源，便于人工复核与审计追溯。
        </Paragraph>
      </div>

      {unknownFields.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="仍有数据缺口"
          description={
            <Space wrap style={{ marginTop: 6 }}>
              {unknownFields.map((field) => (
                <Tag key={field}>{UNKNOWN_LABELS[field] || field}</Tag>
              ))}
            </Space>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {evidence.length === 0 ? (
        <Empty description="暂无可复核证据，相关评分维度不得生成分数" />
      ) : (
        evidence.map((item, index) => (
          <Card
            key={item.id}
            className={styles.evidenceCard}
            title={
              <Space wrap>
                <span>{index + 1}. {item.field}</span>
                <Tag color={item.source_type === "synthetic" ? "orange" : "blue"}>
                  {item.source_type === "synthetic" ? "合成演示" : item.source_type}
                </Tag>
              </Space>
            }
            size="small"
          >
            <Title level={5} className={styles.evidenceClaim}>
              {item.claim}
            </Title>
            <Paragraph>{displayValue(item.value)}</Paragraph>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="来源标题">
                {item.source_title}
              </Descriptions.Item>
              <Descriptions.Item label="原始链接">
                {item.source_url ? (
                  <Link href={item.source_url} target="_blank" rel="noreferrer">
                    <LinkOutlined /> 打开原始来源
                  </Link>
                ) : (
                  <Text type="secondary">快照内未记录 URL</Text>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="采集时间">
                {new Date(item.collected_at).toLocaleString("zh-CN")}
              </Descriptions.Item>
              <Descriptions.Item label="采集工具">
                <DatabaseOutlined /> {item.tool}
              </Descriptions.Item>
              <Descriptions.Item label="快照 ID">
                <Text copyable={{ text: item.snapshot_id }}>{item.snapshot_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="证据置信度">
                <Progress
                  percent={Math.round(item.confidence * 100)}
                  size="small"
                  status="normal"
                />
              </Descriptions.Item>
            </Descriptions>
          </Card>
        ))
      )}

      {warnings.length > 0 && (
        <Alert
          type="info"
          showIcon
          message="解释边界"
          description={
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          }
          style={{ marginTop: 16 }}
        />
      )}
    </Drawer>
  );
}
