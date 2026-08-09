import type { Metadata, Viewport } from "next";
import "./globals.css";
import AppLayout from "@/components/layout/AppLayout";
import UiProvider from "@/components/layout/UiProvider";
import { UserProvider } from "@/contexts/UserContext";
import { DataModeProvider } from "@/contexts/DataModeContext";

export const metadata: Metadata = {
  title: "智园领航｜AI产业园运营平台",
  description: "智园领航——面向产业园招商、政策、风险与企业服务的多智能体运营决策平台",
};

export const viewport: Viewport = {
  themeColor: "#0b1d36",
  colorScheme: "light",
};

// Authentication, role permissions and data mode are evaluated at request time.
// Avoid caching an old application shell across frontend releases.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <UiProvider>
          <UserProvider>
            <DataModeProvider>
              <AppLayout>{children}</AppLayout>
            </DataModeProvider>
          </UserProvider>
        </UiProvider>
      </body>
    </html>
  );
}
