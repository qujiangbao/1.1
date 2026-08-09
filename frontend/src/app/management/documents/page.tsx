"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadProps } from "antd";
import {
  CloudUploadOutlined,
  DeleteOutlined,
  FileDoneOutlined,
  FileSearchOutlined,
  FolderOpenOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import PageHeader from "@/components/layout/PageHeader";
import {
  deleteParkDocument,
  listParkDocuments,
  type ParkDocument,
  uploadParkDocument,
} from "@/api/documents.api";

const { Paragraph, Text, Title } = Typography;
const { Dragger } = Upload;

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function ParkDocumentsPage() {
  const [documents, setDocuments] = useState<ParkDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [category, setCategory] = useState("园区综合资料");
  const [tags, setTags] = useState("");
  const [query, setQuery] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setDocuments(await listParkDocuments());
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "资料列表加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return documents;
    return documents.filter((item) =>
      `${item.name} ${item.category} ${item.tags.join(" ")} ${item.excerpt}`.toLowerCase().includes(normalized),
    );
  }, [documents, query]);

  const uploadProps: UploadProps = {
    multiple: true,
    accept: ".pdf,.docx,.pptx,.txt,.md",
    showUploadList: false,
    customRequest: async ({ file, onSuccess, onError }) => {
      setUploading(true);
      try {
        const record = await uploadParkDocument(file as File, category, tags);
        if (record.duplicate) {
          message.info(`${record.name} 与资料库现有内容重复，未再次导入`);
        } else if (record.status === "READY") {
          setDocuments((current) => [record, ...current]);
          const structured = record.structured_enterprises
            ? `，识别 ${record.structured_enterprises} 家企业、${record.structured_risk_events || 0} 条风险事件`
            : "";
          message.success(`${record.name} 已解析并加入资料库${structured}`);
        } else {
          setDocuments((current) => [record, ...current]);
          message.warning(`${record.name} 已保存，但文本解析失败`);
        }
        onSuccess?.(record);
      } catch (reason) {
        const error = reason instanceof Error ? reason : new Error("上传失败");
        message.error(error.message);
        onError?.(error);
      } finally {
        setUploading(false);
      }
    },
  };

  const remove = async (record: ParkDocument) => {
    try {
      await deleteParkDocument(record.id);
      setDocuments((current) => current.filter((item) => item.id !== record.id));
      message.success("资料及解析文本已删除");
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "删除失败");
    }
  };

  return (
    <div className="document-library-page">
      <PageHeader
        title="园区资料库"
        description="把园区已有的规划、招商手册、企业材料和政策文件变成可检索、可引用的 AI 决策依据。"
        backTo="/dashboard"
        backLabel="运营总览"
        extra={<Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>刷新</Button>}
      />

      <section className="document-library-hero">
        <div>
          <span><SafetyCertificateOutlined /> PARK-OWNED KNOWLEDGE</span>
          <Title level={2}>园区自己的资料，直接交给 AI 使用</Title>
          <Paragraph>文件保存于园区服务器，解析后会参与政策与资料检索；原始文件、解析状态、来源人员和文件指纹均可追溯。</Paragraph>
        </div>
        <div className="document-library-metrics">
          <Statistic title="已导入资料" value={documents.length} suffix="份" />
          <Statistic title="可检索资料" value={documents.filter((item) => item.status === "READY").length} suffix="份" />
          <Statistic title="已提取文本" value={documents.reduce((total, item) => total + item.text_length, 0)} formatter={(value) => `${Math.round(Number(value) / 10000)} 万字`} />
        </div>
      </section>

      <Row gutter={[18, 18]}>
        <Col xs={24} lg={9}>
          <Card className="document-upload-card">
            <div className="document-card-heading"><CloudUploadOutlined /><div><strong>导入园区资料</strong><span>单文件不超过 25 MB</span></div></div>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Select
                value={category}
                onChange={setCategory}
                style={{ width: "100%" }}
                options={["园区规划", "招商资料", "企业资料", "政策文件", "会议纪要", "园区综合资料"].map((value) => ({ value }))}
              />
              <Input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="资料标签，用逗号分隔，例如：机器人，招商，2026" />
              <Dragger {...uploadProps} disabled={uploading}>
                <p className="ant-upload-drag-icon"><CloudUploadOutlined /></p>
                <p className="ant-upload-text">点击或拖拽文件到这里</p>
                <p className="ant-upload-hint">支持 PDF、DOCX、PPTX、TXT、Markdown，可一次选择多个文件</p>
              </Dragger>
            </Space>
            <Alert
              type="warning"
              showIcon
              message="导入格式与解析要求"
              description={(
                <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                  <li>支持 PDF、DOCX、PPTX、TXT、Markdown，单文件不超过 25 MB。</li>
                  <li>TXT 和 Markdown 必须使用 UTF-8 编码；扫描图片型 PDF 暂不支持 OCR。</li>
                  <li>文件中必须包含可提取文字；分类可选，标签最多读取 20 个。</li>
                  <li>分类决定资料用途：“政策文件”进入政策匹配，“企业资料”进入企业画像与风险证据。</li>
                  <li>园区规划、招商资料和会议纪要主要用于检索引用；“园区综合资料”会按标题、标签和正文结构判断是否同时补充企业或政策线索。</li>
                  <li>Markdown 中以企业名称为二级标题、以表格列出工商/审核字段时，可自动结构化。</li>
                  <li>系统按文件指纹和规范化正文去重；重复内容不会再次写入。</li>
                </ul>
              )}
              style={{ marginTop: 16 }}
            />
            <Alert type="info" showIcon message="导入不是直接相信" description="AI 检索会标明资料来源；重要招商结论仍需人工核验原文和有效期。" style={{ marginTop: 16 }} />
          </Card>
        </Col>

        <Col xs={24} lg={15}>
          <Card className="document-list-card" title={<><FolderOpenOutlined /> 资料清单</>} extra={<Input allowClear prefix={<FileSearchOutlined />} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索名称、标签或摘要" style={{ width: 260 }} />}>
            <Table
              rowKey="id"
              loading={loading}
              dataSource={filtered}
              pagination={{ pageSize: 8, hideOnSinglePage: true }}
              locale={{ emptyText: <Empty description="还没有导入园区资料" /> }}
              columns={[
                {
                  title: "资料",
                  dataIndex: "name",
                  render: (_value, record) => (
                    <div className="document-name-cell">
                      <FileDoneOutlined />
                      <div>
                        <strong>{record.name}</strong>
                        <span>{record.excerpt || record.error || "等待提取文本"}</span>
                        {(record.structured_enterprises || record.structured_risk_events) ? (
                          <span style={{ color: "#28796f", marginTop: 3 }}>
                            已结构化：{record.structured_enterprises || 0} 家企业 · {record.structured_risk_events || 0} 条风险事件
                          </span>
                        ) : null}
                      </div>
                    </div>
                  ),
                },
                { title: "分类", dataIndex: "category", width: 120, render: (value) => <Tag>{value}</Tag> },
                { title: "状态", dataIndex: "status", width: 100, render: (value) => <Tag color={value === "READY" ? "success" : "error"}>{value === "READY" ? "可检索" : "解析失败"}</Tag> },
                { title: "大小", dataIndex: "file_size", width: 90, render: formatSize },
                {
                  title: "操作",
                  width: 74,
                  render: (_value, record) => (
                    <Popconfirm title="删除这份资料？" description="原始文件和已提取文本都会删除，无法恢复。" okText="删除" cancelText="取消" okButtonProps={{ danger: true }} onConfirm={() => void remove(record)}>
                      <Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除 ${record.name}`} />
                    </Popconfirm>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
