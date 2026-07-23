# Industrial Park Agent — 测试计划

## 测试策略

| 层级 | 工具 | 范围 | 状态 |
|------|------|------|:---:|
| 语法 | py_compile | 全部 .py | ✅ 37/37 |
| 结构 | Node.js fs check | 全部 .tsx | ✅ 14/14 |
| 导入 | import | 全部模块 | ✅ |
| API | urllib | 12 端点 | ✅ |
| Agent | LangGraph invoke | 7 个图 | ✅ |

## API 测试用例

### Agent Chat
```
输入: "帮我寻找广州机器人产业链企业"
预期: status=completed, agents_used包含InvestmentAgent
```

### Investment Search
```
输入: {"keyword": "机器人", "industry": "robotics"}
预期: success=true, data.enterprises数组
```

### Risk Analyze
```
输入: {"enterprise_id": "E001"}
预期: success=true, data.risk_score为数字
```

### Policy Search
```
输入: {"query": "机器人产业补贴"}
预期: success=true, data.policies数组
```

### Industry Analyze
```
输入: {"industry": "机器人"}
预期: success=true, data.report含trend_score
```

### Service Request
```
输入: {"request": "申请研发补贴"}
预期: success=true, data.ticket_id存在
```

### Dashboard Overview
```
请求: GET /api/v1/dashboard/overview
预期: success=true, data.park_overview有数据
```

## 前端验收

| 页面 | 路由 | 验收项 |
|------|------|--------|
| AI Chat | /agent/chat | 输入框可用，消息发送，Agent动画，Markdown渲染 |
| Agent Trace | /agent/trace/:id | Timeline展示，步骤卡片 |
| Dashboard | /dashboard | KPI卡片，招商/风险表格 |
| Enterprise | /enterprise/:id | 企业信息，评分展示 |
| Investment | /dashboard/investment | 招商数据卡片 |
| Risk | /dashboard/risk | 风险分布卡片 |
