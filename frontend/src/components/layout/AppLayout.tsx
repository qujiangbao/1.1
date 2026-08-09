"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Drawer,
  Dropdown,
  Grid,
  Spin,
  Tag,
} from "antd";
import type { MenuProps } from "antd";
import {
  AlertOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  CheckSquareOutlined,
  CustomerServiceOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DownOutlined,
  FolderOpenOutlined,
  LogoutOutlined,
  MenuOutlined,
  PlayCircleOutlined,
  RobotOutlined,
  SearchOutlined,
  SettingOutlined,
  SyncOutlined,
  TeamOutlined,
  UserOutlined,
  WifiOutlined,
} from "@ant-design/icons";
import { useUserContext } from "@/contexts/UserContext";

const ROLE_MENU_ACCESS: Record<string, string[]> = {
  "/agent/workspace": ["super_admin", "park_manager", "investment_manager", "policy_manager", "enterprise_service", "viewer"],
  "/dashboard": ["super_admin", "park_manager", "investment_manager", "policy_manager", "enterprise_service", "viewer"],
  "/agent/chat": ["super_admin", "park_manager", "investment_manager", "policy_manager", "enterprise_service", "viewer"],
  "/agent/team": ["super_admin", "park_manager"],
  "/dashboard/investment": ["super_admin", "park_manager", "investment_manager"],
  "/dashboard/risk": ["super_admin", "park_manager", "investment_manager"],
  "/dashboard/bi": ["super_admin", "park_manager", "investment_manager", "policy_manager", "enterprise_service", "viewer"],
  "/investment/tasks": ["super_admin", "park_manager", "investment_manager"],
  "/service-tickets": ["super_admin", "park_manager", "enterprise_service"],
  "/management/policies": ["super_admin", "park_manager", "policy_manager"],
  "/management/policy-updates": ["super_admin"],
  "/management/documents": ["super_admin", "park_manager", "policy_manager", "investment_manager"],
  "/management/users": ["super_admin"],
};

const navGroups = [
  {
    key: "command",
    label: "运营指挥",
    icon: <AppstoreOutlined />,
    items: [
      { key: "/agent/workspace", icon: <PlayCircleOutlined />, label: "园区决策工作台", description: "一句需求，调度 AI 团队" },
      { key: "/dashboard", icon: <DashboardOutlined />, label: "园区运营总览", description: "总览机会、风险与任务" },
      { key: "/agent/chat", icon: <RobotOutlined />, label: "AI 运营助手", description: "连续对话与专业研判" },
    ],
  },
  {
    key: "business",
    label: "招商经营",
    icon: <SearchOutlined />,
    items: [
      { key: "/dashboard/investment", icon: <SearchOutlined />, label: "招商决策中心", description: "产业链寻商与企业评分" },
      { key: "/dashboard/risk", icon: <AlertOutlined />, label: "企业风险监测", description: "风险证据与处置建议" },
      { key: "/dashboard/bi", icon: <BarChartOutlined />, label: "经营分析看板", description: "经营指标与趋势洞察" },
      { key: "/investment/tasks", icon: <CheckSquareOutlined />, label: "招商跟进", description: "目标企业推进闭环" },
      { key: "/service-tickets", icon: <CustomerServiceOutlined />, label: "企业服务工单", description: "企业诉求受理与办结" },
    ],
  },
  {
    key: "governance",
    label: "资源治理",
    icon: <DatabaseOutlined />,
    items: [
      { key: "/agent/team", icon: <TeamOutlined />, label: "智能体团队", description: "查看角色与协作分工" },
      { key: "/management/policies", icon: <DatabaseOutlined />, label: "惠企政策库", description: "政策正文与匹配依据" },
      { key: "/management/policy-updates", icon: <SyncOutlined />, label: "政策更新中心", description: "政府政策采集、去重与入库" },
      { key: "/management/documents", icon: <FolderOpenOutlined />, label: "园区资料库", description: "导入并检索园区自有资料" },
      { key: "/management/users", icon: <SettingOutlined />, label: "组织与权限", description: "账号角色与访问范围" },
    ],
  },
];

const ROLE_LABELS: Record<string, string> = {
  super_admin: "超级管理员",
  park_manager: "产业园经理",
  investment_manager: "招商经理",
  policy_manager: "政策经理",
  enterprise_service: "企业服务",
  viewer: "只读用户",
};

const PAGE_META = [
  { match: "/agent/workspace", title: "园区决策工作台", section: "运营指挥" },
  { match: "/agent/trace", title: "Agent 执行链路", section: "运营指挥" },
  { match: "/agent/chat", title: "AI 运营助手", section: "运营指挥" },
  { match: "/agent/team", title: "智能体团队", section: "资源治理" },
  { match: "/dashboard/investment", title: "招商决策中心", section: "招商经营" },
  { match: "/dashboard/risk", title: "企业风险监测", section: "招商经营" },
  { match: "/dashboard/bi", title: "经营分析看板", section: "招商经营" },
  { match: "/investment/tasks", title: "招商跟进", section: "招商经营" },
  { match: "/service-tickets", title: "企业服务工单", section: "招商经营" },
  { match: "/management/policies", title: "惠企政策库", section: "资源治理" },
  { match: "/management/policy-updates", title: "政策更新中心", section: "资源治理" },
  { match: "/management/documents", title: "园区资料库", section: "资源治理" },
  { match: "/management/users", title: "组织与权限", section: "资源治理" },
  { match: "/enterprise", title: "企业决策档案", section: "招商经营" },
  { match: "/dashboard", title: "园区运营总览", section: "运营指挥" },
];

type NavItem = (typeof navGroups)[number]["items"][number];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const screens = Grid.useBreakpoint();
  const isDesktop = screens.lg !== false;
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [online, setOnline] = useState(true);
  const { user, authenticated, ready, clearSession } = useUserContext();
  const authRoute = pathname.startsWith("/auth/");

  useEffect(() => {
    if (authRoute || !ready || authenticated) return;
    const returnTo = pathname === "/" ? "/dashboard" : pathname;
    router.replace(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
  }, [authRoute, authenticated, pathname, ready, router]);

  useEffect(() => setMobileMenuOpen(false), [pathname]);

  useEffect(() => {
    const update = () => setOnline(window.navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  const groups = useMemo(
    () => navGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => !user || ROLE_MENU_ACCESS[item.key]?.includes(user.role)),
      }))
      .filter((group) => group.items.length > 0),
    [user],
  );

  const activeItem = useMemo(() => {
    if (pathname === "/") return groups.flatMap((group) => group.items).find((item) => item.key === "/dashboard");
    return groups
      .flatMap((group) => group.items)
      .sort((a, b) => b.key.length - a.key.length)
      .find((item) => pathname === item.key || pathname.startsWith(`${item.key}/`));
  }, [groups, pathname]);

  const activeGroup = groups.find((group) => group.items.some((item) => item.key === activeItem?.key));
  const pageMeta = [...PAGE_META]
    .sort((a, b) => b.match.length - a.match.length)
    .find((item) => pathname === item.match || pathname.startsWith(`${item.match}/`)) || PAGE_META[PAGE_META.length - 1];

  const handleLogout = () => {
    clearSession();
    router.replace("/auth/login");
  };

  const accountMenu: MenuProps = {
    items: [
      {
        key: "identity",
        disabled: true,
        label: (
          <div className="account-menu-identity">
            <strong>{user?.display_name || user?.username}</strong>
            <span>{ROLE_LABELS[user?.role || ""] || user?.role}</span>
          </div>
        ),
      },
      { type: "divider" },
      { key: "logout", icon: <LogoutOutlined />, label: "退出登录", danger: true, onClick: handleLogout },
    ],
  };

  const openItem = (item: NavItem) => router.push(item.key);

  const dropdownMenu = (items: NavItem[]): MenuProps => ({
    className: "product-nav-menu",
    selectedKeys: activeItem ? [activeItem.key] : [],
    items: items.map((item) => ({
      key: item.key,
      icon: item.icon,
      label: (
        <div className="product-nav-menu-copy">
          <strong>{item.label}</strong>
          <span>{item.description}</span>
        </div>
      ),
      onClick: () => openItem(item),
    })),
  });

  if (authRoute) return <>{children}</>;
  if (!ready || !authenticated) {
    return (
      <div className="app-auth-loading">
        <div className="app-loading-mark">智</div>
        <Spin size="large" />
        <span>正在进入园区运营中枢</span>
      </div>
    );
  }

  return (
    <div className="app-shell app-shell-horizontal">
      <a className="skip-link" href="#main-content">跳到主要内容</a>

      <header className="product-header">
        <div className="product-header-inner">
          <button className="product-brand" type="button" onClick={() => router.push("/agent/workspace")}>
            <span className="product-brand-mark">智</span>
            <span className="product-brand-copy">
              <strong>智园领航</strong>
              <small>AI 产业园运营平台</small>
            </span>
          </button>

          {isDesktop ? (
            <nav className="product-nav" aria-label="主导航">
              {groups.map((group) => (
                <Dropdown key={group.key} menu={dropdownMenu(group.items)} placement="bottom" trigger={["hover", "click"]}>
                  <button className="product-nav-group" data-active={activeGroup?.key === group.key || undefined} type="button">
                    {group.icon}<span>{group.label}</span><DownOutlined />
                  </button>
                </Dropdown>
              ))}
            </nav>
          ) : (
            <Button className="product-mobile-trigger" type="text" icon={<MenuOutlined />} onClick={() => setMobileMenuOpen(true)} aria-label="打开导航" />
          )}

          <div className="product-actions">
            <Tag color="blue">公开数据与园区资料</Tag>
            {!online && <Tag color="error">离线</Tag>}
            <Dropdown menu={accountMenu} placement="bottomRight" trigger={["click"]}>
              <button className="account-trigger" type="button" aria-label="打开账号菜单">
                <Badge dot color={online ? "#4f8f7a" : "#c85b5b"} offset={[-3, 31]}>
                  <Avatar size={36} icon={<UserOutlined />} />
                </Badge>
                {isDesktop && <span className="account-trigger-copy"><strong>{user?.display_name || user?.username}</strong><small>{ROLE_LABELS[user?.role || ""] || "园区用户"}</small></span>}
                {isDesktop && <DownOutlined className="account-trigger-arrow" />}
              </button>
            </Dropdown>
          </div>
        </div>
      </header>

      <Drawer className="product-mobile-drawer" placement="left" width={310} open={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} closable={false}>
        <div className="mobile-brand-row">
          <span className="product-brand-mark">智</span>
          <div><strong>智园领航</strong><small>AI 产业园运营平台</small></div>
        </div>
        <nav className="mobile-product-nav">
          {groups.map((group) => (
            <section key={group.key}>
              <h2>{group.label}</h2>
              {group.items.map((item) => (
                <button key={item.key} type="button" data-active={activeItem?.key === item.key || undefined} onClick={() => openItem(item)}>
                  <span>{item.icon}</span><div><strong>{item.label}</strong><small>{item.description}</small></div>
                </button>
              ))}
            </section>
          ))}
        </nav>
      </Drawer>

      {!online && <Alert className="global-system-alert" type="error" banner showIcon icon={<WifiOutlined />} message="网络连接已断开，写操作将在网络恢复后可用。" />}
      <div className="product-pagebar">
        <div><span>{pageMeta.section}</span><i>/</i><strong>{pageMeta.title}</strong></div>
        <p>让园区运营从发现问题，快速走到决策与行动</p>
      </div>

      <main id="main-content" className="app-main-content product-main-content">{children}</main>
    </div>
  );
}
