"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Layout, Menu, Button, Tag } from "antd";
import {
  DashboardOutlined, RobotOutlined, SearchOutlined, AlertOutlined,
  TeamOutlined, MenuFoldOutlined, MenuUnfoldOutlined, PlayCircleOutlined,
  BarChartOutlined, SettingOutlined, LogoutOutlined,
} from "@ant-design/icons";
import { useUserContext } from "@/contexts/UserContext";

const { Sider, Content, Header } = Layout;

// P4: 角色-菜单可见性映射
const ROLE_MENU_ACCESS: Record<string, string[]> = {
  "/agent/workspace":      ["super_admin", "park_manager", "investment_manager", "policy_manager", "enterprise_service", "viewer"],
  "/dashboard":            ["super_admin", "park_manager", "investment_manager", "policy_manager", "enterprise_service", "viewer"],
  "/agent/chat":           ["super_admin", "park_manager", "investment_manager", "policy_manager", "enterprise_service", "viewer"],
  "/agent/team":           ["super_admin", "park_manager"],
  "/dashboard/investment": ["super_admin", "park_manager", "investment_manager"],
  "/dashboard/risk":       ["super_admin", "park_manager", "investment_manager"],
  "/dashboard/bi":         ["super_admin", "park_manager", "investment_manager", "policy_manager", "enterprise_service", "viewer"],
};

const allMenuItems = [
  { key: "/agent/workspace",      icon: <PlayCircleOutlined />, label: "比赛工作台" },
  { key: "/dashboard",            icon: <DashboardOutlined />,  label: "园区总览" },
  { key: "/agent/chat",           icon: <RobotOutlined />,      label: "AI运营中心" },
  { key: "/agent/team",           icon: <TeamOutlined />,       label: "Agent 团队" },
  { key: "/dashboard/investment", icon: <SearchOutlined />,     label: "招商驾驶舱" },
  { key: "/dashboard/risk",       icon: <AlertOutlined />,      label: "风险预警" },
  { key: "/dashboard/bi",         icon: <BarChartOutlined />,   label: "BI 驾驶舱" },
];

const ROLE_LABELS: Record<string, string> = {
  super_admin: "超级管理员",
  park_manager: "产业园经理",
  investment_manager: "招商经理",
  policy_manager: "政策经理",
  enterprise_service: "企业服务",
  viewer: "只读用户",
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { user, setUser } = useUserContext();

  if (pathname.startsWith("/auth/")) return <>{children}</>;

  // P4: 按角色过滤菜单
  const visibleMenuItems = allMenuItems.filter(item => {
    const allowed = ROLE_MENU_ACCESS[item.key];
    if (!allowed) return true;
    if (!user) return true; // 未加载时显示全部
    return allowed.includes(user.role);
  });

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
    setUser(null);
    router.replace("/auth/login");
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="dark" width={220}
        style={{ overflow: "auto", height: "100vh", position: "fixed", left: 0, top: 0, bottom: 0, zIndex: 10 }}>
        <div style={{ height: 64, display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontSize: collapsed ? 14 : 17, fontWeight: 700, whiteSpace: "nowrap",
          borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
          {collapsed ? "广智" : "广州产业AI运营官"}
        </div>
        <Menu theme="dark" mode="inline"
          selectedKeys={[pathname === "/" ? "/dashboard" : pathname]}
          items={visibleMenuItems}
          onClick={({ key }) => router.push(key)}
          style={{ marginTop: 8 }} />
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 80 : 220, transition: "margin-left 0.2s" }}>
        <Header style={{ background: "#fff", padding: "0 24px", display: "flex",
          alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #f0f0f0",
          position: "sticky", top: 0, zIndex: 9 }}>
          <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)} />
          <span style={{ fontSize: 15, fontWeight: 600 }}>
            Industrial Park Agent v2.0
            {user && (
              <Tag color="blue" style={{ marginLeft: 12 }}>
                {ROLE_LABELS[user.role] || user.role}
              </Tag>
            )}
          </span>
          <Button type="text" icon={<LogoutOutlined />} onClick={handleLogout}
            title="退出登录" style={{ color: "#999" }} />
        </Header>

        <Content style={{ margin: 24, padding: 24, background: "#fff", borderRadius: 8, minHeight: 280 }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
