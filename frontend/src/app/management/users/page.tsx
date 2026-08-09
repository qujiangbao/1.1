"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Avatar,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";

import {
  createManagedUser,
  deleteManagedUser,
  getManagedUsers,
  updateManagedUser,
} from "@/api/management.api";
import PageHeader from "@/components/layout/PageHeader";
import { useUserContext } from "@/contexts/UserContext";
import type { ManagedUser } from "@/types/management";

const ROLES = [
  { value: "super_admin", label: "超级管理员" },
  { value: "park_manager", label: "产业园经理" },
  { value: "investment_manager", label: "招商经理" },
  { value: "policy_manager", label: "政策经理" },
  { value: "enterprise_service", label: "企业服务" },
  { value: "viewer", label: "只读用户" },
];

const ROLE_LABELS = Object.fromEntries(
  ROLES.map(({ value, label }) => [value, label]),
);

const ROLE_COLORS: Record<string, string> = {
  super_admin: "gold",
  park_manager: "cyan",
  investment_manager: "green",
  policy_manager: "purple",
  enterprise_service: "blue",
  viewer: "default",
};

interface AccountFormValues {
  username: string;
  display_name?: string;
  password?: string;
  role: string;
  park_id?: string;
  is_active?: boolean;
}

function accountInitials(account: ManagedUser) {
  const label = (account.display_name || account.username).trim();
  return label.slice(0, 1).toUpperCase() || "U";
}

export default function UserManagementPage() {
  const { user: currentUser } = useUserContext();
  const [form] = Form.useForm<AccountFormValues>();
  const [items, setItems] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  const [query, setQuery] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setItems(await getManagedUsers());
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "账号加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const filteredItems = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return items;
    return items.filter((account) =>
      [
        account.username,
        account.display_name,
        ROLE_LABELS[account.role],
        account.park_id,
      ].some((value) => value?.toLowerCase().includes(keyword)),
    );
  }, [items, query]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ role: "viewer", is_active: true });
    setEditorOpen(true);
  };

  const openEdit = (account: ManagedUser, focusPassword = false) => {
    setEditing(account);
    form.setFieldsValue({
      username: account.username,
      display_name: account.display_name || undefined,
      role: account.role,
      park_id: account.park_id || undefined,
      is_active: account.is_active,
      password: undefined,
    });
    setEditorOpen(true);
    if (focusPassword) {
      window.setTimeout(() => form.scrollToField("password"), 120);
    }
  };

  const closeEditor = () => {
    if (saving) return;
    setEditorOpen(false);
    setEditing(null);
    form.resetFields();
  };

  const saveAccount = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (!editing) {
        await createManagedUser({
          username: values.username.trim(),
          password: values.password || "",
          display_name: values.display_name?.trim() || undefined,
          role: values.role,
          park_id: values.park_id?.trim() || undefined,
        });
        message.success("账号已创建");
      } else {
        const securityProtected =
          editing.user_id === currentUser?.id || editing.user_id === "user-admin-001";
        const changes = securityProtected
          ? {
              display_name: values.display_name?.trim() || null,
              park_id: values.park_id?.trim() || null,
            }
          : {
              username: values.username.trim(),
              display_name: values.display_name?.trim() || null,
              role: values.role,
              park_id: values.park_id?.trim() || null,
              is_active: Boolean(values.is_active),
              ...(values.password ? { password: values.password } : {}),
            };
        await updateManagedUser(editing.user_id, changes);
        message.success(values.password ? "账号资料与密码已更新" : "账号资料已更新");
      }
      closeEditor();
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const changeStatus = async (account: ManagedUser, is_active: boolean) => {
    setUpdatingId(account.user_id);
    try {
      await updateManagedUser(account.user_id, { is_active });
      message.success(is_active ? "账号已启用" : "账号已停用");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "状态更新失败");
    } finally {
      setUpdatingId(null);
    }
  };

  const removeAccount = async (account: ManagedUser) => {
    setDeletingId(account.user_id);
    try {
      await deleteManagedUser(account.user_id);
      message.success(`账号 @${account.username} 已删除`);
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "删除失败");
    } finally {
      setDeletingId(null);
    }
  };

  const columns: ColumnsType<ManagedUser> = [
    {
      title: "账号",
      key: "account",
      width: 290,
      render: (_, account) => {
        const isCurrent = account.user_id === currentUser?.id;
        return (
          <div className="account-identity">
            <Avatar className="account-list-avatar">{accountInitials(account)}</Avatar>
            <div className="account-identity-copy">
              <div className="account-name-line">
                <strong>{account.display_name || account.username}</strong>
                {isCurrent && <Tag className="account-current-tag">当前账号</Tag>}
              </div>
              <span>@{account.username}</span>
            </div>
          </div>
        );
      },
    },
    {
      title: "角色与范围",
      key: "role",
      width: 230,
      render: (_, account) => (
        <div className="account-role-cell">
          <Tag color={ROLE_COLORS[account.role]}>
            {ROLE_LABELS[account.role] || account.role}
          </Tag>
          <span>{account.park_id ? `园区：${account.park_id}` : "全部园区"}</span>
        </div>
      ),
    },
    {
      title: "访问状态",
      dataIndex: "is_active",
      width: 150,
      render: (active: boolean, account) => {
        const isCurrent = account.user_id === currentUser?.id;
        return (
          <Tooltip title={isCurrent ? "当前登录账号不可停用" : undefined}>
            <Switch
              checked={active}
              loading={updatingId === account.user_id}
              disabled={isCurrent || updatingId === account.user_id}
              checkedChildren="已启用"
              unCheckedChildren="已停用"
              onChange={(next) => void changeStatus(account, next)}
            />
          </Tooltip>
        );
      },
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 180,
      render: (value?: string | null) =>
        value ? new Date(value).toLocaleString("zh-CN") : "—",
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 280,
      render: (_, account) => {
        const isCurrent = account.user_id === currentUser?.id;
        const isBootstrap = account.user_id === "user-admin-001";
        const securityProtected = isCurrent || isBootstrap;
        return (
          <Space size={4} className="account-actions">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => openEdit(account)}
            >
              编辑
            </Button>
            <Tooltip
              title={
                isCurrent
                  ? "当前账号请通过个人安全设置修改密码"
                  : isBootstrap
                    ? "系统初始管理员的密码由部署环境统一维护"
                    : undefined
              }
            >
              <Button
                type="text"
                icon={<KeyOutlined />}
                disabled={securityProtected}
                onClick={() => openEdit(account, true)}
              >
                重置密码
              </Button>
            </Tooltip>
            <Popconfirm
              title="删除这个账号？"
              description={`删除后 @${account.username} 将无法登录，此操作不可撤销。`}
              okText="确认删除"
              cancelText="取消"
              okButtonProps={{ danger: true, loading: deletingId === account.user_id }}
              disabled={isCurrent || isBootstrap}
              onConfirm={() => removeAccount(account)}
            >
              <Tooltip
                title={
                  isCurrent
                    ? "不能删除当前登录账号"
                    : isBootstrap
                      ? "系统初始管理员受保护"
                      : undefined
                }
              >
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  disabled={isCurrent || isBootstrap}
                >
                  删除
                </Button>
              </Tooltip>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  const activeCount = items.filter((account) => account.is_active).length;
  const adminCount = items.filter((account) => account.role === "super_admin").length;
  const editingCurrent = editing?.user_id === currentUser?.id;
  const editingBootstrap = editing?.user_id === "user-admin-001";
  const editingSecurityProtected = editingCurrent || editingBootstrap;

  return (
    <div className="account-management-page">
      <PageHeader
        title="账号与权限"
        description="统一维护登录账号、岗位角色、园区范围与访问状态。"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建账号
            </Button>
          </Space>
        }
      />

      <div className="account-summary-grid">
        <Card className="account-summary-card">
          <TeamOutlined />
          <div><strong>{items.length}</strong><span>全部账号</span></div>
        </Card>
        <Card className="account-summary-card account-summary-card-active">
          <UserOutlined />
          <div><strong>{activeCount}</strong><span>正常使用</span></div>
        </Card>
        <Card className="account-summary-card account-summary-card-admin">
          <SafetyCertificateOutlined />
          <div><strong>{adminCount}</strong><span>超级管理员</span></div>
        </Card>
      </div>

      <Card className="account-table-card">
        <div className="account-toolbar">
          <div>
            <h3>账号目录</h3>
            <p>编辑资料、重置密码、启停或删除账号；关键管理员受到安全保护。</p>
          </div>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            value={query}
            placeholder="搜索姓名、账号、角色或园区"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <Table
          rowKey="user_id"
          loading={loading}
          columns={columns}
          dataSource={filteredItems}
          pagination={{
            pageSize: 10,
            showSizeChanger: false,
            hideOnSinglePage: true,
            showTotal: (value) => `共 ${value} 个账号`,
          }}
          scroll={{ x: 1130 }}
          locale={{ emptyText: <Empty description="没有匹配的账号" /> }}
        />
      </Card>

      <Modal
        className="account-editor-modal"
        title={editing ? "编辑账号" : "新建账号"}
        open={editorOpen}
        confirmLoading={saving}
        okText={editing ? "保存修改" : "创建账号"}
        cancelText="取消"
        onOk={() => void saveAccount()}
        onCancel={closeEditor}
        maskClosable={!saving}
        destroyOnClose
      >
        {editingSecurityProtected && (
          <div className="account-self-notice">
            {editingCurrent
              ? "当前登录账号只能修改显示名称和园区范围，登录名、密码、角色与状态已保护。"
              : "系统初始管理员由部署环境维护，只能修改显示名称和园区范围。"}
          </div>
        )}
        <Form<AccountFormValues>
          form={form}
          layout="vertical"
          requiredMark="optional"
        >
          <div className="account-form-grid">
            <Form.Item
              name="username"
              label="登录账号"
              rules={[
                { required: true, message: "请输入登录账号" },
                { min: 2, message: "至少输入 2 个字符" },
                { pattern: /^[A-Za-z0-9._-]+$/, message: "仅支持字母、数字、点、短横线和下划线" },
              ]}
            >
              <Input autoComplete="off" disabled={editingSecurityProtected} placeholder="例如：investment.li" />
            </Form.Item>
            <Form.Item name="display_name" label="显示名称">
              <Input placeholder="例如：李明" />
            </Form.Item>
          </div>

          <Form.Item
            name="password"
            label={editing ? "重置密码" : "初始密码"}
            extra={editing ? "留空表示不修改原密码" : "至少 8 位，建议包含字母、数字和符号"}
            rules={editing ? [{ min: 8, message: "密码至少 8 位" }] : [
              { required: true, message: "请设置初始密码" },
              { min: 8, message: "密码至少 8 位" },
            ]}
          >
            <Input.Password
              autoComplete="new-password"
              disabled={editingSecurityProtected}
              placeholder={editing ? "输入新密码（可选）" : "设置初始密码"}
            />
          </Form.Item>

          <div className="account-form-grid">
            <Form.Item name="role" label="岗位角色" rules={[{ required: true }]}>
              <Select options={ROLES} disabled={editingSecurityProtected} />
            </Form.Item>
            <Form.Item name="park_id" label="园区范围" extra="留空表示可访问全部园区">
              <Input placeholder="例如：park-guangzhou-01" />
            </Form.Item>
          </div>

          {editing && (
            <Form.Item name="is_active" label="访问状态" valuePropName="checked">
              <Switch
                disabled={editingSecurityProtected}
                checkedChildren="允许登录"
                unCheckedChildren="禁止登录"
              />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
}
