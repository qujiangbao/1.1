"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Progress,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tooltip,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  AlertOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  RobotOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import PageHeader from "@/components/layout/PageHeader";
import { apiJson } from "@/api/fetch";
import { useDataMode } from "@/contexts/DataModeContext";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

type RiskLevel = "high" | "medium" | "low";

interface RiskEnterprise {
  risk_id: number | string;
  enterprise_id: string;
  name: string;
  score: number;
  level: RiskLevel;
  reason: string;
  risk_type?: string | null;
  source?: string | null;
  created_at?: string | null;
  trend: string;
  action: string;
}

interface RiskDashboardData {
  data_available: boolean;
  is_demo: boolean;
  disclaimer?: string | null;
  scenario_id?: string | null;
  total_enterprises: number;
  evaluated_enterprises: number;
  coverage_pct: number;
  distribution: Record<RiskLevel, number>;
  enterprises: RiskEnterprise[];
  summary: string;
  insights: string[];
  source: string;
  generated_at: string;
}

const levelLabel: Record<RiskLevel, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};

const levelColor: Record<RiskLevel, string> = {
  high: "red",
  medium: "orange",
  low: "blue",
};

export default function RiskDashboard() {
  const router = useRouter();
  const { mode, isDemo } = useDataMode();
  const [data, setData] = useState<RiskDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedLevel, setSelectedLevel] = useState<RiskLevel | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await apiJson<{ success: boolean; data: RiskDashboardData }>(
        `${API}/dashboard/risk?limit=50&mode=${mode}`,
      );
      setData(response.data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "风险数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredEnterprises = useMemo(
    () =>
      selectedLevel
        ? (data?.enterprises || []).filter(
            (enterprise) => enterprise.level === selectedLevel,
          )
        : data?.enterprises || [],
    [data, selectedLevel],
  );

  const columns: ColumnsType<RiskEnterprise> = [
    {
      title: "排名",
      key: "rank",
      width: 56,
      fixed: "left",
      render: (_value, _record, index) => (
        <span style={{ color: "#999", fontSize: 12 }}>#{index + 1}</span>
      ),
    },
    {
      title: "企业名称",
      dataIndex: "name",
      key: "name",
      width: 180,
      ellipsis: true,
      render: (name, record) => (
        isDemo ? (
          <span>{name}</span>
        ) : (
          <Button
            type="link"
            style={{ padding: 0 }}
            onClick={() =>
              router.push(
                `/enterprise/${encodeURIComponent(record.enterprise_id)}?returnTo=${encodeURIComponent("/dashboard/risk")}`,
              )
            }
          >
            {name}
          </Button>
        )
      ),
    },
    {
      title: data?.source === "park_document_evidence" ? "证据风险指标" : "风险评分",
      dataIndex: "score",
      key: "score",
      width: 140,
      render: (score: number, record) => (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Progress
            percent={score}
            size="small"
            strokeColor={
              record.level === "high"
                ? "#ff4d4f"
                : record.level === "medium"
                  ? "#fa8c16"
                  : "#1677ff"
            }
            style={{ flex: 1, margin: 0 }}
          />
          <span style={{ fontSize: 12, fontWeight: 600, minWidth: 36 }}>{score}%</span>
        </div>
      ),
    },
    {
      title: "等级",
      dataIndex: "level",
      key: "level",
      width: 80,
      render: (level: RiskLevel) => (
        <Tag color={levelColor[level]}>{levelLabel[level] || level}</Tag>
      ),
    },
    {
      title: "风险原因",
      dataIndex: "reason",
      key: "reason",
      width: 220,
      ellipsis: { showTitle: false },
      render: (reason: string) => (
        <Tooltip title={reason} placement="topLeft">
          <span>{reason}</span>
        </Tooltip>
      ),
    },
    {
      title: "建议行动",
      dataIndex: "action",
      key: "action",
      width: 220,
      ellipsis: { showTitle: false },
      render: (action: string) => (
        <Tooltip title={action} placement="topLeft">
          <Tag color="blue" style={{ maxWidth: "100%", overflow: "hidden", textOverflow: "ellipsis" }}>
            {action}
          </Tag>
        </Tooltip>
      ),
    },
    {
      title: "更新时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 140,
      render: (value?: string) => (
        <span style={{ fontSize: 12, color: "#999", whiteSpace: "nowrap" }}>
          {value ? new Date(value).toLocaleString("zh-CN") : "—"}
        </span>
      ),
    },
  ];

  const evaluated = data?.evaluated_enterprises || 0;
  const distribution = data?.distribution || { high: 0, medium: 0, low: 0 };
  const progress = (count: number) =>
    evaluated ? Math.round((count / evaluated) * 100) : 0;

  return (
    <div>
      <PageHeader
        title={<><AlertOutlined style={{ color: "#ff4d4f", marginRight: 8 }} />企业风险监测</>}
        description={
          isDemo
            ? "展示固定合成场景中的风险发现、筛选与人工复核流程"
            : data?.source === "park_document_evidence"
              ? "展示园区资料库中可追溯的公开风险证据；指标为事件严重度映射，不是预测分"
              : "展示 risk 表中每家企业的最新真实评估记录"
        }
        backLabel="返回园区运营总览"
        extra={
          <Tooltip
            title={
              data?.data_available
                ? ""
                : "当前没有可供分析的真实风险评估记录"
            }
          >
            <span>
              <Button
                type="primary"
                icon={<RobotOutlined />}
                disabled={!data?.data_available}
                onClick={() =>
                  router.push(
                    `/agent/chat?prompt=${encodeURIComponent("分析园区现有高风险企业并给出处置建议")}`,
                  )
                }
              >
                AI 深度分析
              </Button>
            </span>
          </Tooltip>
        }
      />

      {error && (
        <Alert
          type="error"
          showIcon
          message="风险数据加载失败"
          description={error}
          action={<Button onClick={loadData}>重试</Button>}
          style={{ marginBottom: 16 }}
        />
      )}

      <Spin spinning={loading}>
        {data && !data.data_available && (
          <Card
            size="small"
            title="风险画像待建立"
            style={{ marginBottom: 16, borderLeft: "4px solid #1677ff" }}
          >
            <p style={{ marginBottom: 6 }}>{data.summary}</p>
            <span style={{ color: "#666" }}>
              当前处于公开快照模式，未使用演示企业或虚构风险数量。接入风险评估记录后将自动更新。
            </span>
          </Card>
        )}

        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          {(["high", "medium", "low"] as RiskLevel[]).map((level) => (
            <Col xs={24} md={12} xl={6} key={level}>
              <Card
                hoverable={Boolean(data?.data_available)}
                onClick={() => data?.data_available && setSelectedLevel(level)}
                style={{
                  borderColor: selectedLevel === level ? "#1677ff" : undefined,
                }}
              >
                <Statistic
                  title={`${levelLabel[level]}${isDemo ? "示例企业" : "企业"}`}
                  value={data?.data_available ? distribution[level] : "—"}
                  suffix={data?.data_available ? "家" : ""}
                  valueStyle={{
                    color:
                      level === "high"
                        ? "#ff4d4f"
                        : level === "medium"
                          ? "#fa8c16"
                          : "#52c41a",
                  }}
                  prefix={
                    level === "high" ? (
                      <ExclamationCircleOutlined />
                    ) : level === "medium" ? (
                      <WarningOutlined />
                    ) : (
                      <CheckCircleOutlined />
                    )
                  }
                />
              </Card>
            </Col>
          ))}
          <Col xs={24} md={12} xl={6}>
            <Card hoverable onClick={() => setSelectedLevel(null)}>
              <Statistic
                title="已评估 / 企业总数"
                value={data?.data_available ? evaluated : "待接入"}
                suffix={
                  data?.data_available
                    ? `/ ${data?.total_enterprises || 0} 家`
                    : ` / ${data?.total_enterprises || 0} 家企业快照`
                }
                valueStyle={{ color: "#1677ff" }}
              />
              <Progress
                percent={data?.coverage_pct || 0}
                size="small"
                style={{ marginTop: 8 }}
              />
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} lg={12}>
            <Card title="风险等级分布" size="small">
              {(["high", "medium", "low"] as RiskLevel[]).map((level) => (
                <div
                  key={level}
                  style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}
                >
                  <Tag color={levelColor[level]}>{levelLabel[level]}</Tag>
                  <Progress
                    percent={progress(distribution[level])}
                    size="small"
                    style={{ flex: 1, margin: 0 }}
                  />
                  <span style={{ width: 48, textAlign: "right" }}>
                    {data?.data_available ? `${distribution[level]} 家` : "—"}
                  </span>
                </div>
              ))}
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card title="风险数据说明" size="small" style={{ borderLeft: "4px solid #1677ff" }}>
              <p>{data?.summary || "正在加载风险数据…"}</p>
              <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                {(data?.insights || []).map((insight) => (
                  <li key={insight}>{insight}</li>
                ))}
              </ul>
            </Card>
          </Col>
        </Row>

        <Card
          title={<><ExclamationCircleOutlined style={{ color: "#ff4d4f", marginRight: 8 }} />{isDemo ? "演示风险企业记录" : "真实风险企业记录"}</>}
          extra={
            <Space>
              <Tag>{selectedLevel ? `已筛选：${levelLabel[selectedLevel]}` : "全部等级"}</Tag>
              {data && (
                <Tag color={isDemo ? "orange" : "green"}>
                  来源：{data.source === "park_document_evidence" ? "园区资料库公开证据" : data.source}
                </Tag>
              )}
            </Space>
          }
        >
          <Table<RiskEnterprise>
            rowKey="risk_id"
            dataSource={filteredEnterprises}
            columns={columns}
            size="small"
            scroll={{ x: 1036 }}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            locale={{
              emptyText: (
                <Empty description={isDemo ? "演示场景暂无记录" : "尚无已入库或已导入的企业风险证据"} />
              ),
            }}
          />
        </Card>
      </Spin>
    </div>
  );
}
