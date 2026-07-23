import type { Metadata } from "next";
import "./globals.css";
import AppLayout from "@/components/layout/AppLayout";

export const metadata: Metadata = {
  title: "广州产业AI运营官",
  description: "Industrial Park Agent — 产业园多智能体AI运营系统",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body style={{ margin: 0 }}><AppLayout>{children}</AppLayout></body>
    </html>
  );
}
