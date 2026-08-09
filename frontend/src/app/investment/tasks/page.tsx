"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { CheckOutlined, PlusOutlined, SyncOutlined } from "@ant-design/icons";
import { getCandidates } from "@/api/investment.api";
import {
  createFollowUpTask,
  getFollowUpTasks,
  updateFollowUpTask,
} from "@/api/management.api";
import PageHeader from "@/components/layout/PageHeader";
import { useDataMode } from "@/contexts/DataModeContext";
import { useUserContext } from "@/contexts/UserContext";
import type { InvestmentCandidate } from "@/types/investment";
import type {
  FollowUpTask,
  FollowUpTaskStatus,
} from "@/types/management";

const { Paragraph, Text } = Typography;

const COLUMNS: Array<{
  status: FollowUpTaskStatus;
  label: string;
  color: string;
}> = [
  { status: "TODO", label: "待处理", color: "default" },
  { status: "IN_PROGRESS", label: "进行中", color: "processing" },
  { status: "DONE", label: "已完成", color: "success" },
  { status: "CANCELLED", label: "已取消", color: "error" },
];

const PRIORITY_COLOR = {
  LOW: "default",
  MEDIUM: "blue",
  HIGH: "orange",
  URGENT: "red",
} as const;

export default function InvestmentTaskBoardPage() {
  const { mode } = useDataMode();
  const { user, canAccess } = useUserContext();
  const canWrite = canAccess([
    "super_admin",
    "park_manager",
    "investment_manager",
  ]);
  const [form] = Form.useForm();
  const [tasks, setTasks] = useState<FollowUpTask[]>([]);
  const [candidates, setCandidates] = useState<InvestmentCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [completionTask, setCompletionTask] = useState<FollowUpTask | null>(null);
  const [completionNote, setCompletionNote] = useState("");
  const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null);

  const candidateById = useMemo(
    () => new Map(candidates.map((item) => [item.id, item])),
    [candidates],
  );

  const load = async () => {
    setLoading(true);
    try {
      const [nextTasks, candidateList] = await Promise.all([
        getFollowUpTasks(mode),
        getCandidates(mode),
      ]);
      setTasks(nextTasks);
      setCandidates(candidateList.items);
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "任务看板加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [mode]);

  const create = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await createFollowUpTask({
        ...values,
        owner_id: values.owner_id || user?.id,
        due_at: values.due_at?.toISOString(),
        data_mode: mode,
      });
      message.success("跟进任务已创建");
      setOpen(false);
      form.resetFields();
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "创建失败");
    } finally {
      setSaving(false);
    }
  };

  const changeStatus = async (
    task: FollowUpTask,
    status: FollowUpTaskStatus,
  ) => {
    setUpdatingTaskId(task.id);
    try {
      await updateFollowUpTask(task.id, { status });
      message.success("任务状态已更新");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "更新失败");
    } finally {
      setUpdatingTaskId(null);
    }
  };

  const complete = async () => {
    if (!completionTask || !completionNote.trim()) {
      message.error("请填写完成结果");
      return;
    }
    setSaving(true);
    try {
      await updateFollowUpTask(completionTask.id, {
        status: "DONE",
        completion_note: completionNote.trim(),
      });
      setCompletionTask(null);
      setCompletionNote("");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "完成任务失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="招商跟进任务看板"
        description="任务与候选企业、负责人和截止时间关联；状态变更写入审计记录。"
        extra={
          <Space>
            <Button
              icon={<SyncOutlined spin={loading} />}
              loading={loading}
              disabled={loading}
              onClick={() => void load()}
            >
              刷新
            </Button>
            {canWrite && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  form.setFieldsValue({
                    owner_id: user?.id,
                    priority: "MEDIUM",
                  });
                  setOpen(true);
                }}
              >
                新建任务
              </Button>
            )}
          </Space>
        }
      />
      <Row gutter={[14, 14]}>
        {COLUMNS.map((column) => {
          const columnTasks = tasks.filter(
            (task) => task.status === column.status,
          );
          return (
            <Col xs={24} md={12} xl={6} key={column.status}>
              <Card
                loading={loading}
                title={
                  <Space>
                    <Tag color={column.color}>{column.label}</Tag>
                    <Text type="secondary">{columnTasks.length}</Text>
                  </Space>
                }
                styles={{ body: { background: "#f6f8fb", minHeight: 420 } }}
              >
                {columnTasks.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  columnTasks.map((task) => {
                    const candidate = candidateById.get(task.candidate_id);
                    return (
                      <Card
                        key={task.id}
                        size="small"
                        style={{ marginBottom: 10 }}
                      >
                        <Space wrap size={[5, 5]}>
                          <Tag color={PRIORITY_COLOR[task.priority]}>
                            {task.priority}
                          </Tag>
                          {task.due_at && (
                            <Tag color={new Date(task.due_at).getTime() < Date.now() && task.status !== "DONE" ? "red" : undefined}>
                              截止 {new Date(task.due_at).toLocaleDateString("zh-CN")}
                            </Tag>
                          )}
                        </Space>
                        <Paragraph strong style={{ margin: "9px 0 4px" }}>
                          {task.title}
                        </Paragraph>
                        <Text type="secondary">
                          {candidate?.enterprise_name || task.candidate_id}
                        </Text>
                        <div style={{ marginTop: 8 }}>
                          <Text type="secondary">负责人：{task.owner_id}</Text>
                        </div>
                        {task.completion_note && (
                          <AlertResult text={task.completion_note} />
                        )}
                        {canWrite && task.status === "TODO" && (
                          <Button
                            block
                            size="small"
                            type="primary"
                            loading={updatingTaskId === task.id}
                            disabled={Boolean(updatingTaskId)}
                            style={{ marginTop: 10 }}
                            onClick={() => void changeStatus(task, "IN_PROGRESS")}
                          >
                            开始跟进
                          </Button>
                        )}
                        {canWrite && task.status === "IN_PROGRESS" && (
                          <Button
                            block
                            size="small"
                            icon={<CheckOutlined />}
                            disabled={Boolean(updatingTaskId)}
                            style={{ marginTop: 10 }}
                            onClick={() => setCompletionTask(task)}
                          >
                            填写结果并完成
                          </Button>
                        )}
                      </Card>
                    );
                  })
                )}
              </Card>
            </Col>
          );
        })}
      </Row>

      <Modal
        title="新建跟进任务"
        open={open}
        confirmLoading={saving}
        okText="创建任务"
        onOk={() => void create()}
        onCancel={() => setOpen(false)}
        maskClosable={!saving}
        afterClose={() => form.resetFields()}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="candidate_id"
            label="候选企业"
            rules={[{ required: true }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              options={candidates.map((candidate) => ({
                value: candidate.id,
                label: candidate.enterprise_name,
              }))}
              notFoundContent="候选池暂无企业，请先在招商决策中心确认候选"
            />
          </Form.Item>
          <Form.Item name="title" label="任务标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="跟进要求">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="owner_id" label="负责人ID" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="due_at" label="截止时间">
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="priority" label="优先级" rules={[{ required: true }]}>
            <Select
              options={["LOW", "MEDIUM", "HIGH", "URGENT"].map((value) => ({
                value,
                label: value,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="填写完成结果"
        open={Boolean(completionTask)}
        confirmLoading={saving}
        okText="确认完成"
        onOk={() => void complete()}
        onCancel={() => setCompletionTask(null)}
        maskClosable={!saving}
        afterClose={() => setCompletionNote("")}
      >
        <Input.TextArea
          rows={5}
          value={completionNote}
          placeholder="记录联系结果、企业反馈和下一阶段结论"
          onChange={(event) => setCompletionNote(event.target.value)}
        />
      </Modal>
    </div>
  );
}

function AlertResult({ text }: { text: string }) {
  return (
    <div
      style={{
        marginTop: 9,
        padding: 8,
        borderRadius: 6,
        background: "#f6ffed",
        color: "#237804",
        fontSize: 12,
      }}
    >
      完成结果：{text}
    </div>
  );
}
