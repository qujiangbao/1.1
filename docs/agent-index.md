# Industrial Park Agent — Agent 索引

> 版本：V1.3 | 共 7 个 Agent（1 Supervisor + 6 Business）

---

## Supervisor Agent（AI 运营总经理）

| 属性 | 值 |
|------|-----|
| 节点 | 7 个（Industry → Investment → Risk → Policy → Service → BI → Aggregator） |
| 编排 | LangGraph StateGraph |
| 接口 | `execute_business_agent(agent_name, task, state)` |
| 设计文档 | `docs/architecture/Supervisor_Technical_Design_V1.1.md` |

**职责**：意图识别 → 任务规划 → Agent 路由 → 结果聚合

---

## 6 个业务 Agent

### 1. Policy Agent（AI 政策顾问）

| 属性 | 值 |
|------|-----|
| 工作流 | PDF 解析 → 向量嵌入 → pgvector 检索 → 政策匹配 → 申报建议 |
| 数据源 | Crawl4AI 广州政府政策缓存（222 份 Markdown） |
| 技术 | pgvector HNSW + RAG |
| RAG 模式 | `crawl4ai` / `pgvector` / `mock` |
| 设计文档 | `docs/agents/Policy_RAG_Workflow_V1.0.md` |

### 2. Investment Agent（AI 招商经理）

| 属性 | 值 |
|------|-----|
| 工作流 | 企业搜索 → 企业画像 → 招商评分 → 推荐排序 → 策略生成 |
| 设计文档 | `docs/agents/Investment_Agent_Workflow_V1.0.md` |

### 3. Industry Agent（AI 产业研究院）

| 属性 | 值 |
|------|-----|
| 工作流 | 产业链分析 → 知识图谱 → 趋势预测 → 招商方向推荐 |
| 设计文档 | `docs/agents/Industry_Agent_Technical_Design_V1.0.md` |

### 4. Risk Agent（企业风险雷达）

| 属性 | 值 |
|------|-----|
| 工作流 | 6 维风险评分（经营/财务/舆情/法律/人才/市场） → 预警 |
| 设计文档 | `docs/agents/Risk_Agent_Workflow_V1.0.md` |

### 5. Enterprise Service Agent（AI 企业管家）

| 属性 | 值 |
|------|-----|
| 工作流 | 需求理解 → 服务分类 → 工单管理 → 流程自动化 |
| 设计文档 | `docs/agents/Enterprise_Service_Architecture_V1.0.md` |

### 6. BI Agent（AI 数字驾驶舱）

| 属性 | 值 |
|------|-----|
| 工作流 | 5 大维度 30+ KPI → ECharts 可视化 → AI 洞察 |
| 设计文档 | `docs/agents/BI_Agent_Architecture_V1.0.md` |

---

## Agent 通信规则

```
禁止：Agent A → Agent B（直连）
必须：Agent A → Supervisor → Agent B
```

所有 Agent 间通信使用统一 `TaskMessage` 格式（详见 `docs/architecture/Agent_Communication_Contract_V1.0.md`）。

所有数据访问经过 Tool Gateway（18 个 Tool，RBAC 权限矩阵）。详见 `docs/architecture/Tool_Gateway_Design_V1.0.md`。

---

## Tool Gateway 工具矩阵

| 工具类别 | 工具数 | 说明 |
|----------|:---:|------|
| Database Tools | 6 | PostgreSQL CRUD |
| Knowledge Tools | 4 | pgvector 向量检索 |
| Analysis Tools | 5 | 评分/评级/预测 |
| External Tools | 3 | 天眼查/企查查/政府 API |

---

## 设计文档对照

| Agent | V1.0 设计文档（FROZEN） | V1.0 中文草稿（ARCHIVE） |
|-------|------------------------|------------------------|
| Supervisor | `docs/architecture/Supervisor_Technical_Design_V1.1.md` | `docs/archive/v1.0-drafts/Supervisor_Agent_Draft.md` |
| 政策 RAG | `docs/agents/Policy_RAG_Workflow_V1.0.md` | `docs/archive/v1.0-drafts/政策RAG_Agent.md` |
| 招商 | `docs/agents/Investment_Agent_Workflow_V1.0.md` | `docs/archive/v1.0-drafts/招商Agent.md` |
| 产业分析 | `docs/agents/Industry_Agent_Technical_Design_V1.0.md` | `docs/archive/v1.0-drafts/产业分析Agent.md` |
| 风险预警 | `docs/agents/Risk_Agent_Workflow_V1.0.md` | `docs/archive/v1.0-drafts/风险Agent.md` |
| 企业服务 | `docs/agents/Enterprise_Service_Architecture_V1.0.md` | `docs/archive/v1.0-drafts/企业服务Agent.md` |
| BI 驾驶舱 | `docs/agents/BI_Agent_Architecture_V1.0.md` | `docs/archive/v1.0-drafts/BI驾驶舱.md` |
| 总架构师 | — | `docs/archive/v1.0-drafts/总架构师.md` |
| Demo/产品 | `docs/agents/Demo_Product_Agent_Design_V1.0.md` | `docs/archive/v1.0-drafts/比赛Demo与商业方案.md` |

---

> 新增 Agent 必须：1) 写设计文档 → 2) 注册到 AGENT_REGISTRY → 3) 更新本文档
