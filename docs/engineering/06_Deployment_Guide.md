# Industrial Park Agent — Sprint 5 Demo 指南

## 启动步骤

### 1. 启动后端（已运行）
```
http://localhost:8000
```

### 2. 启动前端（Windows PowerShell）
```powershell
cd D:\广智能\frontend
npm run dev
```
访问：http://localhost:3000

### 3. 生成 Demo 数据
```bash
cd D:\广智能\backend
.venv/bin/python3 scripts/seed_demo.py
```

---

## 5 分钟 Demo 操作流程

### 0:00 打开 AI 运营中心
→ 导航到 /agent/chat

### 0:30 输入 Demo 指令
```
帮我寻找广州机器人产业链企业，并评估招商价值与风险
```

### 0:30-1:30 Agent 执行展示
右侧面板实时展示：
- Supervisor → 意图识别
- IndustryAgent → 产业趋势分析
- InvestmentAgent → 企业搜索+评分
- RiskAgent → 风险评估
- PolicyAgent → 政策匹配

### 1:30-2:00 查看结果
- 企业推荐列表
- 招商评分 + 风险评分
- 政策匹配建议

### 2:00-2:30 查看 Trace
→ 点击"查看执行链路"，展示 Agent Trace 页面

### 2:30-3:30 查看 Dashboard
→ 导航到 /dashboard
→ 展示招商驾驶舱 /dashboard/investment
→ 展示风险驾驶舱 /dashboard/risk

### 3:30-4:00 查看企业画像
→ 导航到 /enterprise/E001

### 4:00-5:00 总结
→ 回到 /agent/chat
→ 展示其他查询："这家企业能申请什么补贴？"
→ 政策匹配结果展示

---

## 系统状态检查

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# Agent 状态
curl http://localhost:8000/api/v1/agent/status

# Dashboard 数据
curl http://localhost:8000/api/v1/dashboard/overview
```

## 项目统计

| 指标 | 数值 |
|------|------|
| 设计文档 | 20+ 份 |
| 后端 Python 文件 | 37 个 |
| 前端 TypeScript 文件 | 14 个 |
| API 端点 | 12 个 |
| LangGraph 图 | 7 个（1 Supervisor + 6 Business） |
| Tool Gateway 工具 | 14 个 |
| 数据库表 | 20 张 |
