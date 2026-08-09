"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import {
  CheckCircleOutlined,
  LockOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useUserContext } from "@/contexts/UserContext";
import { saveAuthSession } from "@/lib/authStorage";

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setUser } = useUserContext();

  const submit = async (values: { username: string; password: string }) => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || "用户名或密码错误");
      }
      const data = await response.json();
      saveAuthSession(data.access_token, data.refresh_token, data.user);
      if (data.user) setUser(data.user);
      const requested = new URLSearchParams(window.location.search).get("returnTo");
      const destination = requested?.startsWith("/") && !requested.startsWith("//")
        ? requested
        : "/agent/workspace";
      router.replace(destination);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-shell">
      <section className="login-hero" aria-label="产品介绍">
        <span className="login-eyebrow">智园领航 · SMARTPARK AI</span>
        <Typography.Title className="login-title">
          一句话，调度一支<br /><em>AI 园区运营团队</em>
        </Typography.Title>
        <Typography.Paragraph className="login-subtitle">
          从产业链研判、招商寻商到风险预警与政策匹配，
          把分散的信息、判断与任务连接成一条可追踪的决策链。
        </Typography.Paragraph>
        <div className="login-points">
          <span className="login-point"><RobotOutlined /> 多智能体协作</span>
          <span className="login-point"><SafetyCertificateOutlined /> 证据可追溯</span>
          <span className="login-point"><CheckCircleOutlined /> 业务闭环</span>
        </div>
        <div className="login-metrics" aria-label="平台能力概览">
          <div className="login-metric"><strong>多</strong><span>类业务入口</span></div>
          <div className="login-metric"><strong>6</strong><span>类智能体角色</span></div>
          <div className="login-metric"><strong>持续</strong><span>更新政策公开快照</span></div>
        </div>
      </section>
      <section className="login-panel" aria-label="账号登录">
      <Card className="login-card">
        <div className="login-card-logo">智</div>
        <Space direction="vertical" size={4} style={{ width: "100%", marginBottom: 24 }}>
          <Typography.Text type="secondary">欢迎进入智园领航</Typography.Text>
          <Typography.Title level={2} style={{ margin: 0 }}>登录运营中枢</Typography.Title>
          <Typography.Text type="secondary">使用园区工作账号继续</Typography.Text>
        </Space>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 18 }} role="alert" />}
        <Form onFinish={submit} initialValues={{ username: "admin" }} layout="vertical" size="large">
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" autoFocus aria-label="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" autoComplete="current-password" aria-label="密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} disabled={loading} block>
            {loading ? "正在进入运营中枢" : "进入运营中枢"}
          </Button>
        </Form>
        <div className="login-security-note">
          <SafetyCertificateOutlined /> 登录状态仅保存在当前设备
        </div>
      </Card>
      </section>
    </main>
  );
}
