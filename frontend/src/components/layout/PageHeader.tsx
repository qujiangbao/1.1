"use client";

import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button, Typography } from "antd";

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
    <header className="page-header">
      <div className="page-header-main">
        <Button
          className="page-header-back"
          aria-label={backLabel}
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          type="text"
        >
          {backLabel}
        </Button>
        <div className="page-header-copy">
          <span className="page-header-eyebrow">SMART PARK · OPERATION INTELLIGENCE</span>
          <Title level={2} className="page-header-title">
            {title}
          </Title>
          {description && (
            <Text type="secondary" className="page-header-description">
              {description}
            </Text>
          )}
        </div>
      </div>
      {extra && <div className="page-header-extra">{extra}</div>}
    </header>
  );
}
