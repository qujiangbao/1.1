import { Card, Col, Row, Skeleton, Space } from "antd";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="页面加载中" style={{ maxWidth: 1450, margin: "0 auto" }}>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Skeleton active title={{ width: 260 }} paragraph={{ rows: 1, width: 520 }} />
        <Card style={{ minHeight: 220 }}><Skeleton active paragraph={{ rows: 4 }} /></Card>
        <Row gutter={[16, 16]}>
          {[0, 1, 2, 3].map((item) => (
            <Col xs={24} sm={12} xl={6} key={item}><Card><Skeleton active paragraph={{ rows: 2 }} /></Card></Col>
          ))}
        </Row>
      </Space>
    </div>
  );
}
