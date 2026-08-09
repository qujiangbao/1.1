"use client";

import type { ReactNode } from "react";
import { App, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";

export default function UiProvider({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#2f6f64",
          colorInfo: "#3d756c",
          colorSuccess: "#4f8f7a",
          colorWarning: "#c58a42",
          colorError: "#c85b5b",
          colorText: "#1d2926",
          colorTextSecondary: "#6d7772",
          colorBorder: "#dde2dd",
          colorBgLayout: "#f4f2ed",
          colorBgContainer: "#fffefb",
          borderRadius: 10,
          borderRadiusLG: 18,
          controlHeight: 42,
          fontFamily:
            'Inter, "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif',
        },
        components: {
          Button: { fontWeight: 650, primaryShadow: "0 8px 20px rgba(47,111,100,.18)" },
          Card: { headerFontSize: 15, headerFontSizeSM: 14, paddingLG: 22 },
          Menu: { darkItemSelectedBg: "rgba(95,168,154,.16)", itemBorderRadius: 10 },
          Table: { headerBg: "#f2f1ec", headerColor: "#58645f", headerSplitColor: "transparent" },
          Segmented: { itemSelectedBg: "#fffefb", trackBg: "#ecebe5" },
          Input: { activeBorderColor: "#5fa89a", hoverBorderColor: "#8ebfb5" },
          Modal: { borderRadiusLG: 24 },
          Drawer: { colorBgElevated: "#f7f5f0" },
        },
      }}
    >
      <App>{children}</App>
    </ConfigProvider>
  );
}
