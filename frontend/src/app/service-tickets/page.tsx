"use client";

import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Statistic, Table, Tag, message } from "antd";
import { CheckCircleOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";

import PageHeader from "@/components/layout/PageHeader";
import { useUserContext } from "@/contexts/UserContext";
import {
  createServiceTicket,
  listServiceTickets,
  updateServiceTicket,
  type ServiceTicket,
  type TicketPriority,
  type TicketStatus,
} from "@/api/service-tickets.api";

const STATUS: Record<TicketStatus, { label: string; color: string }> = {
  OPEN: { label: "待受理", color: "default" },
  IN_PROGRESS: { label: "处理中", color: "processing" },
  WAITING: { label: "待企业反馈", color: "warning" },
  RESOLVED: { label: "已解决", color: "success" },
  CLOSED: { label: "已关闭", color: "success" },
};
const PRIORITY: Record<TicketPriority, string> = { LOW: "低", MEDIUM: "中", HIGH: "高", URGENT: "紧急" };

export default function ServiceTicketsPage() {
  const { canAccess } = useUserContext();
  const canWrite = canAccess(["super_admin", "park_manager", "enterprise_service"]);
  const [items, setItems] = useState<ServiceTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [resolveTicket, setResolveTicket] = useState<ServiceTicket | null>(null);
  const [resolution, setResolution] = useState("");
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try { setItems(await listServiceTickets(undefined, query)); }
    catch (reason) { message.error(reason instanceof Error ? reason.message : "工单加载失败"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const counts = useMemo(() => ({
    open: items.filter((item) => item.status === "OPEN").length,
    active: items.filter((item) => ["IN_PROGRESS", "WAITING"].includes(item.status)).length,
    done: items.filter((item) => ["RESOLVED", "CLOSED"].includes(item.status)).length,
  }), [items]);

  const create = async () => {
    try {
      const values = await form.validateFields();
      const ticket = await createServiceTicket(values);
      setItems((current) => [ticket, ...current]);
      form.resetFields();
      setCreateOpen(false);
      message.success("企业服务工单已创建");
    } catch (reason) {
      if (reason instanceof Error) message.error(reason.message);
    }
  };

  const changeStatus = async (ticket: ServiceTicket, status: TicketStatus, result?: string) => {
    try {
      const updated = await updateServiceTicket(ticket.id, { status, resolution: result });
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      message.success("工单状态已更新");
    } catch (reason) { message.error(reason instanceof Error ? reason.message : "更新失败"); }
  };

  return (
    <div>
      <PageHeader
        title="企业服务工单"
        description="把企业诉求从 AI 建议转成可指派、可跟进、可办结的真实业务记录。"
        extra={<Space><Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>{canWrite && <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建工单</Button>}</Space>}
      />
      <Alert type="info" showIcon message="AI 不会自动声称服务已经完成" description="工单必须由有权限的工作人员创建或推进，办结时必须填写处理结果。" style={{ marginBottom: 16 }} />
      <Space size={24} style={{ marginBottom: 16 }}>
        <Statistic title="待受理" value={counts.open} />
        <Statistic title="处理中/待反馈" value={counts.active} />
        <Statistic title="已办结" value={counts.done} />
      </Space>
      <Card extra={<Space.Compact><Input allowClear value={query} onChange={(event) => setQuery(event.target.value)} onPressEnter={() => void load()} placeholder="企业、主题或内容" /><Button onClick={() => void load()}>查询</Button></Space.Compact>}>
        <Table rowKey="id" loading={loading} dataSource={items} pagination={{ pageSize: 12 }} columns={[
          { title: "工单", render: (_value, record) => <div><strong>{record.subject}</strong><div style={{ color: "#708078" }}>{record.enterprise_name || "未关联企业"} · {record.category}</div></div> },
          { title: "优先级", dataIndex: "priority", width: 90, render: (value: TicketPriority) => <Tag color={value === "URGENT" ? "error" : value === "HIGH" ? "warning" : undefined}>{PRIORITY[value]}</Tag> },
          { title: "状态", dataIndex: "status", width: 120, render: (value: TicketStatus) => <Tag color={STATUS[value].color}>{STATUS[value].label}</Tag> },
          { title: "负责人", dataIndex: "assignee_id", width: 120, render: (value) => value || "待分配" },
          { title: "更新时间", dataIndex: "updated_at", width: 170, render: (value) => new Date(value).toLocaleString("zh-CN") },
          { title: "操作", width: 210, render: (_value, record) => canWrite ? <Space>{record.status === "OPEN" && <Button size="small" onClick={() => void changeStatus(record, "IN_PROGRESS")}>开始处理</Button>}{!["RESOLVED", "CLOSED"].includes(record.status) && <Button size="small" type="primary" icon={<CheckCircleOutlined />} onClick={() => { setResolveTicket(record); setResolution(""); }}>办结</Button>}</Space> : "—" },
        ]} />
      </Card>

      <Modal title="新建企业服务工单" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => void create()} okText="创建">
        <Form form={form} layout="vertical" initialValues={{ category: "综合服务", priority: "MEDIUM" }}>
          <Form.Item name="enterprise_name" label="企业名称"><Input maxLength={500} /></Form.Item>
          <Form.Item name="subject" label="工单主题" rules={[{ required: true, min: 2 }]}><Input maxLength={300} /></Form.Item>
          <Form.Item name="description" label="企业诉求/问题" rules={[{ required: true, min: 2 }]}><Input.TextArea rows={5} maxLength={10000} showCount /></Form.Item>
          <Form.Item name="category" label="服务分类" rules={[{ required: true }]}><Select options={["综合服务", "政策申报", "场地物业", "人才服务", "融资服务", "技术对接", "行政审批"].map((value) => ({ value }))} /></Form.Item>
          <Form.Item name="priority" label="优先级"><Select options={(Object.keys(PRIORITY) as TicketPriority[]).map((value) => ({ value, label: PRIORITY[value] }))} /></Form.Item>
          <Form.Item name="assignee_id" label="负责人账号ID"><Input maxLength={50} /></Form.Item>
        </Form>
      </Modal>

      <Modal title={`办结工单 · ${resolveTicket?.subject || ""}`} open={Boolean(resolveTicket)} onCancel={() => setResolveTicket(null)} okText="确认办结" onOk={() => { if (!resolution.trim()) { message.warning("请填写处理结果"); return; } if (resolveTicket) void changeStatus(resolveTicket, "RESOLVED", resolution.trim()); setResolveTicket(null); }}>
        <Input.TextArea value={resolution} onChange={(event) => setResolution(event.target.value)} rows={6} maxLength={10000} showCount placeholder="填写已采取的措施、交付结果和后续事项" />
      </Modal>
    </div>
  );
}
