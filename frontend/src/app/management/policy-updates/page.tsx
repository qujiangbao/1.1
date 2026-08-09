"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  CheckOutlined,
  CloseOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
} from "@ant-design/icons";

import {
  createPolicyCrawlRun,
  decidePolicyCrawlerAccess,
  getPolicyCrawlRuns,
  getPolicyCrawlerAccess,
  getPolicyCrawlerAccessRequests,
  getPolicyCrawlerGrants,
  requestPolicyCrawlerAccess,
  revokePolicyCrawlerGrant,
} from "@/api/management.api";
import PageHeader from "@/components/layout/PageHeader";
import { useUserContext } from "@/contexts/UserContext";
import type {
  PolicyCrawlRun,
  PolicyCrawlerAccessRequest,
  PolicyCrawlerAccessState,
  PolicyCrawlerGrant,
} from "@/types/management";

const { Paragraph, Text, Title } = Typography;

const RUN_STATUS: Record<PolicyCrawlRun["status"], { label: string; color: string }> = {
  QUEUED: { label: "等待执行", color: "default" },
  RUNNING: { label: "更新中", color: "processing" },
  SUCCEEDED: { label: "已完成", color: "success" },
  PARTIAL: { label: "部分完成", color: "warning" },
  FAILED: { label: "失败", color: "error" },
};

function statNumber(stats: Record<string, unknown>, key: string) {
  const value = stats[key];
  return typeof value === "number" ? value : 0;
}

export default function PolicyUpdatesPage() {
  const { user } = useUserContext();
  const [access, setAccess] = useState<PolicyCrawlerAccessState | null>(null);
  const [requests, setRequests] = useState<PolicyCrawlerAccessRequest[]>([]);
  const [grants, setGrants] = useState<PolicyCrawlerGrant[]>([]);
  const [runs, setRuns] = useState<PolicyCrawlRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [requestReason, setRequestReason] = useState("需要维护园区惠企政策库并执行增量更新");
  const [pages, setPages] = useState(3);
  const [workers, setWorkers] = useState(3);
  const [force, setForce] = useState(false);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const nextAccess = await getPolicyCrawlerAccess();
      setAccess(nextAccess);
      const tasks: Promise<void>[] = [];
      if (nextAccess.allowed) {
        tasks.push(getPolicyCrawlRuns().then(setRuns));
      } else {
        setRuns([]);
      }
      if (nextAccess.is_root_admin) {
        tasks.push(getPolicyCrawlerAccessRequests().then(setRequests));
        tasks.push(getPolicyCrawlerGrants().then(setGrants));
      } else {
        setRequests([]);
        setGrants([]);
      }
      await Promise.all(tasks);
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "政策更新中心加载失败");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const hasActiveRun = useMemo(
    () => runs.some((run) => run.status === "QUEUED" || run.status === "RUNNING"),
    [runs],
  );

  useEffect(() => {
    if (!hasActiveRun) return;
    const timer = window.setInterval(() => void load(true), 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveRun, load]);

  const submitAccessRequest = async () => {
    if (requestReason.trim().length < 3) {
      message.warning("请填写申请原因");
      return;
    }
    setSubmitting(true);
    try {
      await requestPolicyCrawlerAccess(requestReason.trim());
      message.success("申请已提交，等待初始admin审批");
      await load(true);
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "申请提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const decide = async (requestId: string, decision: "APPROVED" | "REJECTED") => {
    try {
      await decidePolicyCrawlerAccess(requestId, decision);
      message.success(decision === "APPROVED" ? "已批准使用权限" : "已拒绝申请");
      await load(true);
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "审批失败");
    }
  };

  const startRun = async () => {
    setSubmitting(true);
    try {
      await createPolicyCrawlRun({ pages, workers, force });
      message.success("政策更新任务已创建，可离开页面后台继续执行");
      setForce(false);
      await load(true);
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "更新任务创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  const requestColumns: ColumnsType<PolicyCrawlerAccessRequest> = [
    {
      title: "申请账号",
      render: (_, item) => <><Text strong>{item.display_name || item.username}</Text><br /><Text type="secondary">{item.username}</Text></>,
    },
    { title: "申请原因", dataIndex: "reason" },
    { title: "申请时间", dataIndex: "requested_at", render: (value) => new Date(value).toLocaleString("zh-CN") },
    {
      title: "状态",
      dataIndex: "status",
      render: (value) => <Tag color={value === "APPROVED" ? "success" : value === "PENDING" ? "processing" : "default"}>{value}</Tag>,
    },
    {
      title: "操作",
      render: (_, item) => item.status === "PENDING" ? (
        <Space>
          <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => void decide(item.request_id, "APPROVED")}>批准</Button>
          <Button size="small" danger icon={<CloseOutlined />} onClick={() => void decide(item.request_id, "REJECTED")}>拒绝</Button>
        </Space>
      ) : "—",
    },
  ];

  const runColumns: ColumnsType<PolicyCrawlRun> = [
    { title: "开始时间", dataIndex: "created_at", width: 180, render: (value) => new Date(value).toLocaleString("zh-CN") },
    { title: "执行人", dataIndex: "requested_by", width: 150 },
    { title: "范围", width: 130, render: (_, item) => `${item.pages}页 / ${item.workers}并发` },
    { title: "模式", width: 100, render: (_, item) => item.force ? <Tag color="volcano">强制刷新</Tag> : <Tag>增量</Tag> },
    {
      title: "结果",
      render: (_, item) => {
        const status = RUN_STATUS[item.status];
        return <Space direction="vertical" size={2}>
          <Tag color={status.color}>{status.label}</Tag>
          {item.stats && Object.keys(item.stats).length > 0 && (
            <Text type="secondary">
              新抓取 {statNumber(item.stats, "fetched")} · 未变化 {statNumber(item.stats, "unchanged")} · 去重 {statNumber(item.stats, "duplicates")}
            </Text>
          )}
          {item.error && <Text type="danger">{item.error}</Text>}
        </Space>;
      },
    },
  ];

  return (
    <div className="policy-updates-page">
      <PageHeader
        title="政策更新中心"
        description="从广州政府白名单来源增量采集政策，完成跨来源去重、版本识别、入库和审计。"
        extra={<Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>刷新状态</Button>}
      />

      <Alert
        showIcon
        type="info"
        message="爬虫授权、重复政策审核和资格规则人工复核是三项独立控制"
        description="获得爬虫权限只代表可以发起更新；新政策仍需去重判断，正文变化后原有已复核资格规则会自动退回待复核。"
        style={{ marginBottom: 16 }}
      />

      <Card loading={loading} title={<Space><SafetyCertificateOutlined />权限状态</Space>} style={{ marginBottom: 16 }}>
        {access && <Descriptions column={{ xs: 1, md: 3 }}>
          <Descriptions.Item label="当前账号">{user?.display_name || user?.username}</Descriptions.Item>
          <Descriptions.Item label="授权状态">
            <Tag color={access.allowed ? "success" : access.status === "PENDING" ? "processing" : "warning"}>{access.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="说明">{access.reason}</Descriptions.Item>
        </Descriptions>}
        {access && !access.allowed && access.status !== "PENDING" && access.status !== "UNAVAILABLE" && (
          <Space.Compact style={{ width: "100%", marginTop: 12 }}>
            <Input value={requestReason} onChange={(event) => setRequestReason(event.target.value)} placeholder="填写申请原因" />
            <Button type="primary" loading={submitting} onClick={() => void submitAccessRequest()}>申请使用权限</Button>
          </Space.Compact>
        )}
      </Card>

      {access?.allowed && (
        <Card title={<Space><SyncOutlined spin={hasActiveRun} />立即更新政策</Space>} style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]} align="middle">
            <Col><Text>每来源扫描页数</Text><br /><InputNumber min={1} max={20} value={pages} onChange={(value) => setPages(value || 3)} /></Col>
            <Col><Text>并发数</Text><br /><InputNumber min={1} max={3} value={workers} onChange={(value) => setWorkers(value || 3)} /></Col>
            {access.is_root_admin && <Col><Text>强制刷新已有正文</Text><br /><Switch checked={force} onChange={setForce} /></Col>}
            <Col flex="auto">
              <Paragraph type="secondary" style={{ margin: 0 }}>
                普通更新会跳过7天内成功抓取的正文；强制刷新仅初始admin可用。来源固定为广州政府域名白名单。
              </Paragraph>
            </Col>
            <Col>
              <Popconfirm
                title={force ? "确认强制刷新？" : "确认检查政策更新？"}
                description={force ? "将重新抓取近期已经缓存的政策正文。" : "任务将在后台执行。"}
                onConfirm={() => void startRun()}
              >
                <Button type="primary" icon={<SyncOutlined />} loading={submitting} disabled={hasActiveRun}>开始更新</Button>
              </Popconfirm>
            </Col>
          </Row>
        </Card>
      )}

      {access?.is_root_admin && (
        <>
          <Card title={`待审批与历史申请 · ${requests.length}`} style={{ marginBottom: 16 }}>
            <Table rowKey="request_id" columns={requestColumns} dataSource={requests} pagination={{ pageSize: 5 }} />
          </Card>
          <Card title={`已授权超级管理员 · ${grants.filter((item) => item.status === "APPROVED").length}`} style={{ marginBottom: 16 }}>
            <Table
              rowKey="user_id"
              dataSource={grants}
              pagination={false}
              columns={[
                { title: "账号", render: (_, item) => item.display_name || item.username },
                { title: "状态", dataIndex: "status", render: (value) => <Tag color={value === "APPROVED" ? "success" : "default"}>{value}</Tag> },
                { title: "批准时间", dataIndex: "approved_at", render: (value) => new Date(value).toLocaleString("zh-CN") },
                {
                  title: "操作",
                  render: (_, item) => item.status === "APPROVED" ? (
                    <Popconfirm title="确认撤销该账号的爬虫权限？" onConfirm={async () => { await revokePolicyCrawlerGrant(item.user_id); await load(true); }}>
                      <Button danger size="small">撤销权限</Button>
                    </Popconfirm>
                  ) : "—",
                },
              ]}
            />
          </Card>
        </>
      )}

      {access?.allowed && (
        <Card title={<><Title level={5} style={{ display: "inline", margin: 0 }}>更新记录</Title><Text type="secondary"> · 全部操作可追溯</Text></>}>
          <Table
            rowKey="run_id"
            columns={runColumns}
            dataSource={runs}
            pagination={{ pageSize: 10 }}
            expandable={{ expandedRowRender: (item) => <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{JSON.stringify(item.stats, null, 2)}</pre> }}
          />
        </Card>
      )}
    </div>
  );
}
