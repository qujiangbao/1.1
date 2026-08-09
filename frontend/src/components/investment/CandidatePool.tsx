"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Form,
  Grid,
  Input,
  List,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  AuditOutlined,
  EditOutlined,
  FileSearchOutlined,
  ReloadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import {
  getCandidates,
  patchCandidate,
  submitCandidateFeedback,
} from "@/api/investment.api";
import type {
  CandidateStatus,
  DataMode,
  InvestmentCandidate,
} from "@/types/investment";
import EvidenceDrawer from "@/components/investment/EvidenceDrawer";
import styles from "@/components/investment/investment.module.css";

const STATUS_OPTIONS: Array<{ value: CandidateStatus; label: string }> = [
  { value: "NEW", label: "待复核" },
  { value: "REVIEWED", label: "已复核" },
  { value: "CONTACTING", label: "接触中" },
  { value: "NEGOTIATING", label: "洽谈中" },
  { value: "REJECTED", label: "已淘汰" },
  { value: "ARCHIVED", label: "已归档" },
];

const STATUS_COLOR: Record<CandidateStatus, string> = {
  NEW: "blue",
  REVIEWED: "cyan",
  CONTACTING: "gold",
  NEGOTIATING: "orange",
  REJECTED: "red",
  ARCHIVED: "default",
};

interface CandidatePoolProps {
  mode: DataMode;
  canWrite: boolean;
  refreshToken: number;
}

export default function CandidatePool({
  mode,
  canWrite,
  refreshToken,
}: CandidatePoolProps) {
  const screens = Grid.useBreakpoint();
  const compact = !screens.lg;
  const [items, setItems] = useState<InvestmentCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<CandidateStatus | undefined>();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<InvestmentCandidate | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editForm] = Form.useForm();
  const [feedbackForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getCandidates(mode);
      setItems(data.items);
    } catch (reason) {
      setItems([]);
      setError(reason instanceof Error ? reason.message : "候选池加载失败");
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  const filteredItems = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return items.filter((item) => {
      const matchesStatus = !status || item.status === status;
      const matchesQuery =
        !normalized ||
        item.enterprise_name.toLocaleLowerCase().includes(normalized) ||
        (item.industry_chain_role || "").toLocaleLowerCase().includes(normalized) ||
        (item.assignee_id || "").toLocaleLowerCase().includes(normalized);
      return matchesStatus && matchesQuery;
    });
  }, [items, query, status]);

  const metrics = useMemo(
    () => ({
      total: items.length,
      pending: items.filter((item) => item.status === "NEW").length,
      active: items.filter((item) =>
        ["CONTACTING", "NEGOTIATING"].includes(item.status),
      ).length,
      reviewed: items.filter((item) => item.status === "REVIEWED").length,
    }),
    [items],
  );

  const openEvidence = (candidate: InvestmentCandidate) => {
    setSelected(candidate);
    setEvidenceOpen(true);
  };

  const openEdit = (candidate: InvestmentCandidate) => {
    setSelected(candidate);
    editForm.setFieldsValue({
      status: candidate.status,
      assignee_id: candidate.assignee_id,
      next_action: candidate.next_action,
      manual_note: candidate.manual_note,
    });
    setEditOpen(true);
  };

  const openFeedback = (candidate: InvestmentCandidate) => {
    setSelected(candidate);
    feedbackForm.resetFields();
    setFeedbackOpen(true);
  };

  const saveEdit = async () => {
    if (!selected) return;
    const values = await editForm.validateFields();
    setSaving(true);
    try {
      await patchCandidate(selected.id, {
        ...values,
        assignee_id: values.assignee_id || null,
      });
      message.success("候选状态已更新并写入审计日志");
      setEditOpen(false);
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "更新失败");
    } finally {
      setSaving(false);
    }
  };

  const saveFeedback = async () => {
    if (!selected) return;
    const values = await feedbackForm.validateFields();
    setSaving(true);
    try {
      await submitCandidateFeedback(selected.id, values);
      message.success("人工复核反馈已记录");
      setFeedbackOpen(false);
      feedbackForm.resetFields();
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "反馈提交失败");
    } finally {
      setSaving(false);
    }
  };

  const actionButtons = (candidate: InvestmentCandidate) => (
    <Space wrap size={[6, 6]}>
      <Button
        size="small"
        icon={<FileSearchOutlined />}
        onClick={() => openEvidence(candidate)}
      >
        证据
      </Button>
      {canWrite && (
        <>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(candidate)}
          >
            跟进
          </Button>
          <Button
            size="small"
            icon={<AuditOutlined />}
            onClick={() => openFeedback(candidate)}
          >
            复核
          </Button>
        </>
      )}
    </Space>
  );

  const columns: ColumnsType<InvestmentCandidate> = [
    {
      title: "候选企业",
      dataIndex: "enterprise_name",
      width: 230,
      render: (value, row) => (
        <div>
          <Typography.Text strong>{value}</Typography.Text>
          <div style={{ marginTop: 5 }}>
            <Tag>{row.industry_chain_role || "产业链角色待判定"}</Tag>
            {row.data_mode === "demo" && <Tag color="orange">演示</Tag>}
          </div>
        </div>
      ),
    },
    {
      title: "推荐 / 置信",
      width: 130,
      render: (_, row) => (
        <div>
          <Typography.Text strong>
            {row.overall_score == null
              ? "证据不足"
              : `${row.overall_score.toFixed(1)} 分`}
          </Typography.Text>
          <div style={{ color: "#66788a", marginTop: 4 }}>
            置信 {row.confidence == null ? "—" : `${Math.round(row.confidence * 100)}%`}
          </div>
        </div>
      ),
    },
    {
      title: "风险",
      dataIndex: "risk_level",
      width: 95,
      render: (value) => (
        <Tag
          color={
            value === "HIGH"
              ? "red"
              : value === "MEDIUM"
                ? "orange"
                : value === "LOW"
                  ? "green"
                  : "default"
          }
        >
          {value === "UNKNOWN" ? "待核验" : value}
        </Tag>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (value: CandidateStatus) => (
        <Tag color={STATUS_COLOR[value]}>
          {STATUS_OPTIONS.find((item) => item.value === value)?.label || value}
        </Tag>
      ),
    },
    {
      title: "负责人 / 下一步",
      render: (_, row) => (
        <div>
          <div>{row.assignee_id || "未分配"}</div>
          <Typography.Text type="secondary">
            {row.next_action || "待设置跟进行动"}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: "操作",
      width: 230,
      render: (_, row) => actionButtons(row),
    },
  ];

  return (
    <>
      <Card className={styles.poolCard}>
        <div className={styles.poolToolbar}>
          <div>
            <Typography.Text className={styles.sectionKicker}>业务工作台</Typography.Text>
            <Typography.Title level={4} className={styles.sectionTitle}>
              招商候选池
            </Typography.Title>
            <Typography.Text type="secondary">
              从复核、接触到洽谈，统一管理负责人和下一步动作
            </Typography.Text>
          </div>
          <Space wrap>
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="搜索企业、环节或负责人"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              style={{ width: compact ? "100%" : 240 }}
            />
            <Select
              allowClear
              placeholder="全部状态"
              style={{ width: 130 }}
              value={status}
              options={STATUS_OPTIONS}
              onChange={setStatus}
            />
            <Button icon={<ReloadOutlined />} onClick={() => void load()}>
              刷新
            </Button>
          </Space>
        </div>

        <div className={styles.poolSummary}>
          {[
            ["全部候选", metrics.total],
            ["待复核", metrics.pending],
            ["推进中", metrics.active],
            ["已复核", metrics.reviewed],
          ].map(([label, value]) => (
            <div className={styles.poolMetric} key={label}>
              <span className={styles.poolMetricValue}>{value}</span>
              <span className={styles.poolMetricLabel}>{label}</span>
            </div>
          ))}
        </div>

        <Alert
          type={mode === "demo" ? "warning" : "info"}
          showIcon
          message={
            mode === "demo"
              ? "演示候选与公开候选按数据模式严格隔离，不计入真实统计。"
              : "只有用户明确点击“加入候选池”才会形成业务记录，AI 推荐不会自动写入。"
          }
          style={{ marginBottom: 16 }}
        />
        {error && (
          <Alert
            type="error"
            showIcon
            message={error}
            description="请确认数据库持久化服务可用且迁移已完成。"
            style={{ marginBottom: 16 }}
          />
        )}

        {compact ? (
          <List
            loading={loading}
            dataSource={filteredItems}
            locale={{ emptyText: "没有符合当前筛选条件的候选企业" }}
            renderItem={(item) => (
              <Card className={styles.mobileCandidate} size="small">
                <div className={styles.mobileCandidateHeader}>
                  <div>
                    <Typography.Text strong>{item.enterprise_name}</Typography.Text>
                    <div style={{ marginTop: 6 }}>
                      <Tag>{item.industry_chain_role || "角色待判定"}</Tag>
                      <Tag color={STATUS_COLOR[item.status]}>
                        {STATUS_OPTIONS.find((option) => option.value === item.status)
                          ?.label || item.status}
                      </Tag>
                    </div>
                  </div>
                  <Typography.Text strong style={{ color: "#1677ff", fontSize: 20 }}>
                    {item.overall_score == null
                      ? "—"
                      : item.overall_score.toFixed(1)}
                  </Typography.Text>
                </div>
                <div className={styles.mobileCandidateMeta}>
                  <div className={styles.fact}>
                    <span className={styles.factLabel}>负责人</span>
                    <span className={styles.factValue}>
                      {item.assignee_id || "未分配"}
                    </span>
                  </div>
                  <div className={styles.fact}>
                    <span className={styles.factLabel}>风险</span>
                    <span className={styles.factValue}>
                      {item.risk_level === "UNKNOWN" ? "待核验" : item.risk_level}
                    </span>
                  </div>
                </div>
                <Typography.Paragraph
                  type="secondary"
                  ellipsis={{ rows: 2 }}
                  style={{ marginBottom: 12 }}
                >
                  {item.next_action || "待设置跟进行动"}
                </Typography.Paragraph>
                {actionButtons(item)}
              </Card>
            )}
          />
        ) : (
          <Table
            rowKey="id"
            loading={loading}
            dataSource={filteredItems}
            columns={columns}
            pagination={{
              pageSize: 10,
              showSizeChanger: false,
              showTotal: (total) => `共 ${total} 家`,
            }}
            scroll={{ x: 1050 }}
            locale={{ emptyText: "没有符合当前筛选条件的候选企业" }}
          />
        )}
      </Card>

      <EvidenceDrawer
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        title={selected?.enterprise_name || "候选企业"}
        evidence={selected?.evidence || []}
        unknownFields={selected?.unknown_fields || []}
        warnings={selected?.warnings || []}
      />

      <Modal
        open={editOpen}
        title={`推进候选 · ${selected?.enterprise_name || ""}`}
        okText="保存更新"
        cancelText="取消"
        width={560}
        onCancel={() => setEditOpen(false)}
        onOk={() => void saveEdit()}
        confirmLoading={saving}
      >
        <Alert
          type="info"
          showIcon
          message="状态、负责人和行动计划的变更会写入审计日志"
          style={{ marginBottom: 16 }}
        />
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="status"
            label="跟进状态"
            rules={[{ required: true, message: "请选择跟进状态" }]}
          >
            <Select options={STATUS_OPTIONS} />
          </Form.Item>
          <Form.Item name="assignee_id" label="负责人 ID">
            <Input placeholder="例如 investment-manager-01" />
          </Form.Item>
          <Form.Item name="next_action" label="下一步行动">
            <Input.TextArea
              rows={3}
              placeholder="写明动作、对象和预期完成时间"
            />
          </Form.Item>
          <Form.Item name="manual_note" label="人工备注">
            <Input.TextArea rows={3} placeholder="补充跟进背景或判断依据" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={feedbackOpen}
        title={`人工复核 · ${selected?.enterprise_name || ""}`}
        okText="提交复核"
        cancelText="取消"
        width={560}
        onCancel={() => setFeedbackOpen(false)}
        onOk={() => void saveFeedback()}
        confirmLoading={saving}
      >
        <Alert
          type="warning"
          showIcon
          message="复核反馈影响状态与评测，不会修改原始公开数据"
          style={{ marginBottom: 16 }}
        />
        <Form form={feedbackForm} layout="vertical">
          <Form.Item
            name="decision"
            label="复核决定"
            rules={[{ required: true, message: "请选择复核决定" }]}
          >
            <Select
              options={[
                { value: "ACCEPT", label: "采纳" },
                { value: "REJECT", label: "淘汰" },
                { value: "NEED_MORE_EVIDENCE", label: "补充证据" },
                { value: "DEFER", label: "暂缓" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="reason_code"
            label="原因分类"
            rules={[{ required: true, message: "请选择原因分类" }]}
          >
            <Select
              options={[
                { value: "INDUSTRY_FIT", label: "产业匹配" },
                { value: "RISK_TOO_HIGH", label: "风险过高" },
                { value: "INSUFFICIENT_EVIDENCE", label: "证据不足" },
                { value: "POLICY_MISMATCH", label: "政策不匹配" },
                { value: "MANUAL_JUDGEMENT", label: "人工综合判断" },
              ]}
            />
          </Form.Item>
          <Form.Item name="comment" label="复核说明">
            <Input.TextArea rows={4} placeholder="记录判断依据，便于后续追溯" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
