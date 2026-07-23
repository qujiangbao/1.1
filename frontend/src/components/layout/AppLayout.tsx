"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Layout, Menu, Button } from "antd";
import {
  DashboardOutlined,
  RobotOutlined,
  SearchOutlined,
  AlertOutlined,
  TeamOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
} from "@ant-design/icons";

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: "/agent/workspace", icon: <PlayCircleOutlined />, label: "🏆 比赛工作台" },
  { key: "/dashboard", icon: <DashboardOutlined />, label: "园区总览" },
  { key: "/agent/chat", icon: <RobotOutlined />, label: "AI运营中心" },
  { key: "/agent/team", icon: <TeamOutlined />, label: "Agent 团队" },
  { key: "/dashboard/investment", icon: <SearchOutlined />, label: "招商驾驶舱" },
  { key: "/dashboard/risk", icon: <AlertOutlined />, label: "风险预警" },
  { key: "/dashboard/bi", icon: <BarChartOutlined />, label: "BI 驾驶舱" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  if (pathname.startsWith("/auth/")) return <>{children}</>;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="dark"
        width={220}
        style={{
          overflow: "auto",
          height: "100vh",
          position: "fixed",
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      >
        <div
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontSize: collapsed ? 14 : 17,
            fontWeight: 700,
            whiteSpace: "nowrap",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          {collapsed ? "广智" : "广州产业AI运营官"}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[pathname === "/" ? "/dashboard" : pathname]}
          items={menuItems}
          onClick={({ key }) => router.push(key)}
          style={{ marginTop: 8 }}
        />
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 80 : 220, transition: "margin-left 0.2s" }}>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #f0f0f0",
            position: "sticky",
            top: 0,
            zIndex: 9,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <span style={{ fontSize: 15, fontWeight: 600 }}>Industrial Park Agent v2.0</span>
          <span style={{ width: 40 }} />
        </Header>

        <Content style={{ margin: 24, padding: 24, background: "#fff", borderRadius: 8, minHeight: 280 }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
