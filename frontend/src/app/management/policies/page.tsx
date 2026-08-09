"use client";

import { useEffect, useMemo, useState } from "react";
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
  Segmented,
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
  ELIGIBLE: "已确认符合",
  POTENTIALLY_ELIGIBLE: "初步符合",
  INELIGIBLE: "已确认不符合",
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

function enterpriseMatchDisplay(item: PolicyCandidateEligibilityItem) {
  if (item.decision_basis === "PRELIMINARY" && item.preliminary_outcome === "NO_MATCH") {
    return { label: "初步不符合", color: "orange" } as const;
  }
  if (item.preliminary_outcome === "INSUFFICIENT") {
    return { label: "待补资料", color: "default" } as const;
  }
  return {
    label: MATCH_LABELS[item.match_type],
    color: MATCH_COLORS[item.match_type],
  } as const;
}

function conditionDisplay(condition: PolicyCandidateEligibilityItem["condition_results"][number]) {
  if (condition.status === "NEEDS_MANUAL_REVIEW") {
    if (condition.preview_status === "SATISFIED") {
      return { label: "预匹配满足", color: "processing" } as const;
    }
    if (condition.preview_status === "UNSATISFIED") {
      return { label: "预匹配不满足", color: "orange" } as const;
    }
    return { label: "待补证/规则待复核", color: "warning" } as const;
  }
  return {
    label: CONDITION_LABELS[condition.status],
    color:
      condition.status === "SATISFIED"
        ? "success"
        : condition.status === "UNSATISFIED"
          ? "error"
          : "warning",
  } as const;
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
  const [policyView, setPolicyView] = useState<"ELIGIBILITY" | "REFERENCE" | "ALL">("ELIGIBILITY");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<ManagedPolicy | null>(null);
  const [conditionsJson, setConditionsJson] = useState("");
  const [eligibilityPolicy, setEligibilityPolicy] = useState<ManagedPolicy | null>(null);
  const [eligibilityReport, setEligibilityReport] =
    useState<PolicyCandidateEligibilityReport | null>(null);
  const [eligibilityLoading, setEligibilityLoading] = useState(false);
  const [enterpriseQuery, setEnterpriseQuery] = useState("");
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
    setEnterpriseQuery("");
    setEligibilityLoading(true);
    try {
      setEligibilityReport(await getPolicyCandidateEligibility(policy.policy_id));
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "企业适配结果加载失败");
    } finally {
      setEligibilityLoading(false);
    }
  };

  const filteredEnterprises = useMemo(() => {
    if (!eligibilityReport) return [];
    const token = enterpriseQuery.trim().toLowerCase();
    if (!token) return eligibilityReport.items;
    return eligibilityReport.items.filter((item) =>
      `${item.enterprise_name} ${item.enterprise_id}`.toLowerCase().includes(token),
    );
  }, [eligibilityReport, enterpriseQuery]);

  const filteredPolicies = useMemo(() => {
    if (policyView === "ALL") return items;
    if (policyView === "ELIGIBILITY") {
      return items.filter((item) => item.eligibility_mode === "ELIGIBILITY");
    }
    return items.filter((item) => item.eligibility_mode !== "ELIGIBILITY");
  }, [items, policyView]);

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
      title: "自动匹配状态",
      width: 230,
      render: (_, record) => {
        const reviewed = record.eligibility_conditions.filter(
          (condition) => condition.review_status === "REVIEWED",
        ).length;
        const isTemplate = record.conditions_reviewed_by === "template_suggestion";
        if (record.eligibility_mode !== "ELIGIBILITY") {
          return (
            <Space direction="vertical" size={2}>
              <Tag>仅供政策检索</Tag>
              <Text type="secondary">{record.eligibility_mode_reason}</Text>
            </Space>
          );
        }
        return (
          <Space direction="vertical" size={2}>
            <Tag color={reviewed && !isTemplate ? "success" : "processing"}>
              {reviewed && !isTemplate ? "自动匹配 · 规则已确认" : "自动预匹配 · 规则待复核"}
            </Tag>
            <Text type="secondary">
              {reviewed}/{record.eligibility_conditions.length} 条规则已人工确认
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
      width: 280,
      render: (_, record) => (
        <Space>
          <Button
            type="primary"
            icon={<TeamOutlined />}
            disabled={record.eligibility_mode !== "ELIGIBILITY"}
            onClick={() => void openEligibility(record)}
          >
            查看匹配企业
          </Button>
          <Button
            icon={<EditOutlined />}
            disabled={!canWrite || record.eligibility_mode !== "ELIGIBILITY"}
            onClick={() => openEditor(record)}
          >
            规则治理
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="惠企政策库"
        description="企业资料导入后自动参与政策预匹配；从政策反查具体企业、匹配条件和证据缺口。"
        extra={canUpdatePolicies ? <Button href="/management/policy-updates" icon={<SyncOutlined />}>政策更新中心</Button> : undefined}
      />
      <Alert
        type="info"
        showIcon
        message="不需要逐条审核全部政策，也不需要逐家审核企业"
        description="系统会读取园区企业目录（含新导入资料）并自动预匹配。点击“查看匹配企业”可查看谁初步符合、为什么符合以及缺少什么证据；管理员只需在需要正式资格结论时治理政策规则。公示、征求意见、采购和结果类文件仅供检索，不显示资格匹配。"
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
        title={`政策目录 · 当前 ${filteredPolicies.length} 条 / 全部 ${total} 条`}
        extra={
          <Space wrap>
            <Segmented
              value={policyView}
              onChange={(value) => setPolicyView(value as typeof policyView)}
              options={[
                { label: "可匹配政策", value: "ELIGIBILITY" },
                { label: "仅供检索", value: "REFERENCE" },
                { label: "全部", value: "ALL" },
              ]}
            />
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
          </Space>
        }
      >
        <Table
          rowKey="policy_id"
          loading={loading}
          columns={columns}
          dataSource={filteredPolicies}
          pagination={{ pageSize: 20, showSizeChanger: false, showTotal: (value) => `共 ${value} 条` }}
          scroll={{ x: 1120 }}
          locale={{ emptyText: <Empty description={query ? "没有匹配的政策" : "当前分类暂无政策"} /> }}
        />
      </Card>

      <Modal
        width={860}
        title={selected ? `政策资格规则治理 · ${selected.title}` : "政策资格规则治理"}
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
          这里审核的是 AI 从政策原文提取的规则，不是逐家审核企业。规则为 DRAFT 时系统仍会自动预匹配，但只显示“初步”结论；改为 REVIEWED 后才允许输出确定性资格结果。
        </Paragraph>
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
        title={eligibilityPolicy ? `匹配企业 · ${eligibilityPolicy.title}` : "匹配企业"}
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
              message={`自动匹配范围：园区企业目录 ${eligibilityReport.scope_enterprise_count} 家；已计算 ${eligibilityReport.evaluated_enterprise_count} 家`}
              description={
                eligibilityReport.reviewed_condition_count
                  ? `当前共 ${eligibilityReport.condition_count} 条政策规则，其中 ${eligibilityReport.reviewed_condition_count} 条已人工确认。已确认规则可输出正式结论，其余规则继续显示自动预匹配结果。`
                  : "当前规则尚未人工确认，但系统已使用导入的企业字段和证据完成自动预匹配；结果明确标记为“初步”，不会冒充正式资格结论。"
              }
              style={{ marginBottom: 14 }}
            />
            <Space wrap style={{ marginBottom: 14 }}>
              <Tag color="success">已确认符合 {eligibilityReport.eligible_count} 家</Tag>
              <Tag color="processing">初步符合 {eligibilityReport.potential_count} 家</Tag>
              <Tag color="orange">初步不符合 {eligibilityReport.preliminary_ineligible_count} 家</Tag>
              <Tag color="error">已确认不符合 {eligibilityReport.ineligible_count} 家</Tag>
              <Tag>待补资料 {eligibilityReport.insufficient_count} 家</Tag>
            </Space>
            <Input
              allowClear
              value={enterpriseQuery}
              prefix={<SearchOutlined />}
              placeholder="按企业名称或企业ID查找"
              onChange={(event) => setEnterpriseQuery(event.target.value)}
              style={{ marginBottom: 14 }}
            />
            <Table<PolicyCandidateEligibilityItem>
              rowKey="enterprise_id"
              size="small"
              pagination={{ pageSize: 10, showSizeChanger: false, showTotal: (value) => `共 ${value} 家` }}
              dataSource={filteredEnterprises}
              locale={{
                emptyText: (
                  <Empty description={enterpriseQuery ? "没有找到该企业" : "园区企业目录中暂无可匹配数据"} />
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
                  width: 130,
                  render: (_, record) => {
                    const display = enterpriseMatchDisplay(record);
                    return <Tag color={display.color}>{display.label}</Tag>;
                  },
                },
                {
                  title: "为什么",
                  render: (_, record) => (
                    <div>
                      <Text>{record.reason}</Text>
                      {(record.match_score != null || record.matched_terms.length > 0) && (
                        <div>
                          <Text type="secondary">
                            {record.match_score != null ? `条件覆盖 ${Math.round(record.match_score)}%` : ""}
                            {record.match_score != null && record.matched_terms.length ? " · " : ""}
                            {record.matched_terms.length ? `满足：${record.matched_terms.join("、")}` : ""}
                            {record.evidence_count ? ` · ${record.evidence_count} 条企业证据` : ""}
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
                      renderItem={(condition) => {
                        const display = conditionDisplay(condition);
                        return <List.Item>
                          <Space direction="vertical" size={2} style={{ width: "100%" }}>
                            <Space wrap>
                              <Tag color={display.color}>{display.label}</Tag>
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
                        </List.Item>;
                      }}
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
