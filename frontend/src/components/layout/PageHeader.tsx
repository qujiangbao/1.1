"use client";

import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button, Space, Typography } from "antd";

const { Title, Text } = Typography;

interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  backTo?: string;
  backLabel?: string;
  extra?: ReactNode;
}

export default function PageHeader({
  title,
  description,
  backTo = "/dashboard",
  backLabel = "返回",
  extra,
}: PageHeaderProps) {
  const router = useRouter();

  const handleBack = () => {
    // A fixed in-app target is safer than browser history: direct links and
    // links opened from external sites never send the user out of the system.
    router.push(backTo);
  };

  return (
    <div className="page-header">
      <Space align="start" size={12}>
        <Button
          aria-label={backLabel}
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
        >
          {backLabel}
        </Button>
        <div>
          <Title level={2} style={{ margin: 0, fontSize: 24 }}>
            {title}
          </Title>
          {description && (
            <Text type="secondary" style={{ display: "block", marginTop: 4 }}>
              {description}
            </Text>
          )}
        </div>
      </Space>
      {extra && <div className="page-header-extra">{extra}</div>}
    </div>
  );
}
