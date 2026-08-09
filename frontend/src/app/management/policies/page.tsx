"use client";

import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  Empty,
  List,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  EditOutlined,
  SearchOutlined,
  FormatPainterOutlined,
  TeamOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import {
  getManagedPolicies,
  getPolicyCandidateEligibility,
  savePolicyConditions,
} from "@/api/management.api";
import PageHeader from "@/components/layout/PageHeader";
import { useUserContext } from "@/contexts/UserContext";
import type {
  ManagedPolicy,
  ManagedPolicyCondition,
  PolicyCandidateEligibilityItem,
  PolicyCandidateEligibilityReport,
} from "@/types/management";

const { Paragraph, Text } = Typography;

const MATCH_LABELS = {
  ELIGIBLE: "符合",
  POTENTIALLY_ELIGIBLE: "可能符合",
  INELIGIBLE: "不符合",
  RELATED: "仅相关",
  UNKNOWN: "待核验",
} as const;

const MATCH_COLORS = {
  ELIGIBLE: "success",
  POTENTIALLY_ELIGIBLE: "warning",
  INELIGIBLE: "error",
  RELATED: "default",
  UNKNOWN: "default",
} as const;

const CONDITION_LABELS = {
  SATISFIED: "满足",
  UNSATISFIED: "不满足",
  UNKNOWN: "证据不足",
  NEEDS_MANUAL_REVIEW: "条件待人工核对",
  NOT_APPLICABLE: "不适用",
} as const;

function readableValue(value: unknown) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.join("、");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

const CONDITION_TEMPLATE: ManagedPolicyCondition[] = [
  {
    condition_code: "REGISTERED_REGION",
    label: "注册地要求",
    field: "region",
    operator: "IN",
    expected_value: ["广州"],
    mandatory: true,
    review_status: "REVIEWED",
    source_text: "粘贴政策原文中的对应申报条件",
  },
];

export default function PolicyManagementPage() {
  const { canAccess } = useUserContext();
  const canWrite = canAccess(["super_admin", "park_manager", "policy_manager"]);
  const canUpdatePolicies = canAccess(["super_admin"]);
  const [items, setItems] = useState<ManagedPolicy[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<ManagedPolicy | null>(null);
  const [conditionsJson, setConditionsJson] = useState("");
  const [eligibilityPolicy, setEligibilityPolicy] = useState<ManagedPolicy | null>(null);
  const [eligibilityReport, setEligibilityReport] =
    useState<PolicyCandidateEligibilityReport | null>(null);
  const [eligibilityLoading, setEligibilityLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async (nextQuery = query) => {
    setLoading(true);
    setError("");
    try {
      const data = await getManagedPolicies(nextQuery);
      setItems(data.items);
      setTotal(data.total);
    } catch (reason) {
      const detail = reason instanceof Error ? reason.message : "政策加载失败";
      setError(detail);
      message.error(detail);
    } finally {
      setLoading(false);
    }
  };

  const formatConditions = () => {
    try {
      const parsed = JSON.parse(conditionsJson);
      setConditionsJson(JSON.stringify(parsed, null, 2));
      message.success("JSON 格式正确");
    } catch {
      message.error("无法格式化：请先修正 JSON 语法");
    }
  };

  useEffect(() => {
    void load("");
  }, []);

  const openEditor = (policy: ManagedPolicy) => {
    setSelected(policy);
    setConditionsJson(
      JSON.stringify(
        policy.eligibility_conditions.length
          ? policy.eligibility_conditions
          : CONDITION_TEMPLATE,
        null,
        2,
      ),
    );
  };

  const save = async () => {
    if (!selected) return;
    let conditions: ManagedPolicyCondition[];
    try {
      const parsed = JSON.parse(conditionsJson);
      if (!Array.isArray(parsed)) throw new Error();
      conditions = parsed;
    } catch {
      message.error("条件必须是合法的 JSON 数组");
      return;
    }
    setSaving(true);
    try {
      await savePolicyConditions(selected.policy_id, conditions);
      message.success("政策条件已保存，并同步到 Policy Agent 检索分块");
      setSelected(null);
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const openEligibility = async (policy: ManagedPolicy) => {
    setEligibilityPolicy(policy);
    setEligibilityReport(null);
    setEligibilityLoading(true);
    try {
      setEligibilityReport(await getPolicyCandidateEligibility(policy.policy_id));
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "企业适配结果加载失败");
    } finally {
      setEligibilityLoading(false);
    }
  };

  const columns: ColumnsType<ManagedPolicy> = [
    {
      title: "政策",
      dataIndex: "title",
      render: (title: string, record) => (
        <div>
          <Text strong>{title}</Text>
          <div>
            <Text type="secondary">{record.policy_id}</Text>
          </div>
        </div>
      ),
    },
    { title: "发布部门", dataIndex: "department", width: 190, render: (v) => v || "—" },
    {
      title: "条件复核（非企业数）",
      width: 205,
      render: (_, record) => {
        const reviewed = record.eligibility_conditions.filter(
          (condition) => condition.review_status === "REVIEWED",
        ).length;
        const isTemplate = record.conditions_reviewed_by === "template_suggestion";
        return (
          <Space>
            <Tag color={reviewed && !isTemplate ? "success" : "warning"}>
              {isTemplate ? "模板待核对" : `人工已复核 ${reviewed}`}
            </Tag>
            <Text type="secondary">
              共 {record.eligibility_conditions.length} 条
            </Text>
          </Space>
        );
      },
    },
    {
      title: "最近复核",
      dataIndex: "conditions_reviewed_at",
      width: 170,
      render: (value) =>
        value ? new Date(value).toLocaleString("zh-CN") : "尚未复核",
    },
    {
      title: "操作",
      width: 250,
      render: (_, record) => (
        <Space>
          <Button icon={<TeamOutlined />} onClick={() => void openEligibility(record)}>
            谁符合
          </Button>
          <Button
            icon={<EditOutlined />}
            disabled={!canWrite}
            onClick={() => openEditor(record)}
          >
            资格规则审核
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="惠企政策库"
        description="维护政策申报条件与人工复核状态；只有已复核条件才允许进入逐企业自动资格核验。"
        extra={canUpdatePolicies ? <Button href="/management/policy-updates" icon={<SyncOutlined />}>政策更新中心</Button> : undefined}
      />
      <Alert
        type="info"
        showIcon
        message="政策相关不等于具备申报资格"
        description="表格中的数量是政策条件条数，不是符合企业数。点击“谁符合”查看招商候选池中哪些企业曾召回该政策，以及每项条件的要求值、企业实际值和核验依据。DRAFT 条件只提示人工复核，REVIEWED 条件才允许确定性计算。"
        style={{ marginBottom: 16 }}
      />
      {error && (
        <Alert
          type="error"
          showIcon
          message="政策目录加载失败"
          description={error}
          action={<Button onClick={() => void load()}>重试</Button>}
          style={{ marginBottom: 16 }}
        />
      )}
      <Card
        title={`政策目录 · ${total} 条`}
        extra={
          <Space.Compact>
            <Input
              value={query}
              allowClear
              placeholder="政策名称、部门或ID"
              onChange={(event) => setQuery(event.target.value)}
              onClear={() => { setQuery(""); void load(""); }}
              onPressEnter={() => void load()}
            />
            <Button icon={<SearchOutlined />} loading={loading} onClick={() => void load()}>
              查询
            </Button>
          </Space.Compact>
        }
      >
        <Table
          rowKey="policy_id"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={{ pageSize: 20, showSizeChanger: false, showTotal: (value) => `共 ${value} 条` }}
          scroll={{ x: 1120 }}
          locale={{ emptyText: <Empty description={query ? "没有匹配的政策" : "暂无政策数据"} /> }}
        />
      </Card>

      <Modal
        width={860}
        title={selected ? `资格规则审核 · ${selected.title}` : "资格规则审核"}
        open={Boolean(selected)}
        confirmLoading={saving}
        okText="校验并保存"
        onOk={() => void save()}
        onCancel={() => setSelected(null)}
        maskClosable={!saving}
        footer={(_, { OkBtn, CancelBtn }) => (
          <Space>
            <Button icon={<FormatPainterOutlined />} onClick={formatConditions}>格式化并检查</Button>
            <CancelBtn />
            <OkBtn />
          </Space>
        )}
      >
        <Paragraph type="secondary">
          每项需包含 condition_code、label、field、operator、mandatory、
          review_status 和政策原文 source_text。
        </Paragraph>
        <Input.TextArea
          value={conditionsJson}
          onChange={(event) => setConditionsJson(event.target.value)}
          autoSize={{ minRows: 18, maxRows: 28 }}
          spellCheck={false}
          style={{ fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace" }}
        />
      </Modal>

      <Modal
        width={1040}
        title={eligibilityPolicy ? `谁符合 · ${eligibilityPolicy.title}` : "谁符合"}
        open={Boolean(eligibilityPolicy)}
        footer={<Button onClick={() => setEligibilityPolicy(null)}>关闭</Button>}
        onCancel={() => setEligibilityPolicy(null)}
      >
        {eligibilityLoading ? (
          <Card loading />
        ) : eligibilityReport ? (
          <>
            <Alert
              type={eligibilityReport.reviewed_condition_count ? "info" : "warning"}
              showIcon
              message={`核验范围：招商候选池 ${eligibilityReport.scope_candidate_count} 家；与本政策相关 ${eligibilityReport.relevant_candidate_count} 家`}
              description={
                eligibilityReport.reviewed_condition_count
                  ? `当前共 ${eligibilityReport.condition_count} 条政策条件，其中 ${eligibilityReport.reviewed_condition_count} 条已人工复核。只有全部已复核强制条件都有企业证据支持，才显示“符合”。`
                  : "当前没有经过人工复核的政策条件，因此不能判定任何企业“符合”；下方只显示相关企业和待核对项。"
              }
              style={{ marginBottom: 14 }}
            />
            <Space wrap style={{ marginBottom: 14 }}>
              <Tag color="success">符合 {eligibilityReport.eligible_count} 家</Tag>
              <Tag color="warning">待补证/待核验 {eligibilityReport.potential_count} 家</Tag>
              <Tag color="error">不符合 {eligibilityReport.ineligible_count} 家</Tag>
            </Space>
            <Table<PolicyCandidateEligibilityItem>
              rowKey="enterprise_id"
              size="small"
              pagination={false}
              dataSource={eligibilityReport.items}
              locale={{
                emptyText: (
                  <Empty description="候选池中尚无企业完成该政策的相关性检索" />
                ),
              }}
              columns={[
                {
                  title: "企业",
                  dataIndex: "enterprise_name",
                  render: (value: string, record) => (
                    <div>
                      <Text strong>{value}</Text>
                      <div><Text type="secondary">{record.enterprise_id}</Text></div>
                    </div>
                  ),
                },
                {
                  title: "资格判断",
                  dataIndex: "match_type",
                  width: 110,
                  render: (value: PolicyCandidateEligibilityItem["match_type"]) => (
                    <Tag color={MATCH_COLORS[value]}>{MATCH_LABELS[value]}</Tag>
                  ),
                },
                {
                  title: "为什么",
                  render: (_, record) => (
                    <div>
                      <Text>{record.reason}</Text>
                      {(record.match_score != null || record.matched_terms.length > 0) && (
                        <div>
                          <Text type="secondary">
                            {record.match_score != null ? `相关度 ${Math.round(record.match_score)}%` : ""}
                            {record.match_score != null && record.matched_terms.length ? " · " : ""}
                            {record.matched_terms.length ? `命中：${record.matched_terms.join("、")}` : ""}
                          </Text>
                        </div>
                      )}
                    </div>
                  ),
                },
              ]}
              expandable={{
                expandedRowRender: (record) => (
                  record.condition_results.length ? (
                    <List
                      size="small"
                      dataSource={record.condition_results}
                      renderItem={(condition) => (
                        <List.Item>
                          <Space direction="vertical" size={2} style={{ width: "100%" }}>
                            <Space wrap>
                              <Tag
                                color={
                                  condition.status === "SATISFIED"
                                    ? "success"
                                    : condition.status === "UNSATISFIED"
                                      ? "error"
                                      : "warning"
                                }
                              >
                                {CONDITION_LABELS[condition.status]}
                              </Tag>
                              <Text strong>{condition.label || condition.field}</Text>
                              <Text type="secondary">
                                要求：{condition.operator} {readableValue(condition.expected_value)}
                              </Text>
                              <Text type="secondary">
                                企业实际值：{readableValue(condition.actual_value)}
                              </Text>
                            </Space>
                            <Text type="secondary">{condition.reason}</Text>
                            {condition.source_text && (
                              <Text type="secondary">政策依据：{condition.source_text}</Text>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Text type="secondary">尚无可逐条核验的政策条件。</Text>
                  )
                ),
              }}
            />
          </>
        ) : (
          <Empty description="适配结果加载失败" />
        )}
      </Modal>
    </div>
  );
}
