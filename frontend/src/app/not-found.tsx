"use client";

import { Button, Card, Result } from "antd";
import { useRouter } from "next/navigation";

export default function NotFound() {
  const router = useRouter();
  return (
    <div className="state-page">
      <Card className="state-page-card">
        <Result
          status="404"
          title="页面不存在"
          subTitle="链接可能已失效，或当前账号没有对应入口。"
          extra={<Button type="primary" onClick={() => router.replace("/dashboard")}>返回园区运营总览</Button>}
        />
      </Card>
    </div>
  );
}
