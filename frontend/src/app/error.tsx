"use client";

import { Button, Card, Result, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="state-page">
      <Card className="state-page-card">
        <Result
          status="error"
          title="页面暂时无法显示"
          subTitle="数据和登录状态不会因此丢失，可以重新加载当前页面。"
          extra={
            <Button type="primary" icon={<ReloadOutlined />} onClick={reset}>
              重新加载
            </Button>
          }
        />
        {error.message && (
          <Typography.Paragraph type="secondary" copyable={{ text: error.message }}>
            {error.message}
          </Typography.Paragraph>
        )}
      </Card>
    </div>
  );
}
