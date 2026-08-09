# Industrial Park Agent
# Agent Communication Contract V1.0

> 版本：V1.0 | 状态：FROZEN | 适用范围：所有 12 个 Agent
> 
> 本文档是 Industrial Park Agent 系统中所有 Agent 之间通信的唯一规范。
> 任何 Agent 的输入/输出必须符合本协议，Supervisor 据此进行路由和编排。

---

## 1. 核心通信原则

### 原则 1：Supervisor 是唯一调度中心
```
禁止：Agent A → Agent B
必须：Agent A → Supervisor → Agent B
```

### 原则 2：统一消息格式
所有 Agent 间通信使用统一的 TaskMessage 格式，无例外。

### 原则 3：所有数据访问经过 Tool Gateway
```
禁止：Agent → Database
必须：Agent → Supervisor Tool Gateway → Database Tool → Database
```

### 原则 4：全链路可追踪
每次执行必须记录完整的 Agent Trace。

---

## 2. 统一消息格式：TaskMessage

所有 Agent 接收和返回的消息均使用此格式：

```json
{
  "task_id": "TASK-20260721-001",
  "from_agent": "Supervisor",
  "to_agent": "InvestmentAgent",
  "intent": "investment_search",
  "priority": "high",
  "input": {
    "industry": "机器人",
    "region": "广州",
    "target": "产业链企业"
  },
  "expected_output": [
    "enterprise_list",
    "profile",
    "score",
    "strategy"
  ],
  "context": {
    "conversation_id": "CONV-001",
    "user_id": "U001",
    "park_id": "P001"
  },
  "created_at": "2026-07-21T09:00:00Z"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | 是 | 全局唯一任务 ID，格式：TASK-{date}-{seq} |
| from_agent | string | 是 | 发起方 Agent 名称 |
| to_agent | string | 是 | 目标 Agent 名称 |
| intent | string | 是 | 意图分类，决定 Agent 行为 |
| priority | string | 是 | high / medium / low |
| input | object | 是 | 任务输入参数 |
| expected_output | string[] | 是 | 期望返回的能力列表 |
| context | object | 否 | 会话上下文 |
| created_at | string | 是 | ISO 8601 时间戳 |

---

## 3. 统一返回格式：TaskResult

所有 Agent 完成任务后，返回给 Supervisor 的格式：

```json
{
  "task_id": "TASK-20260721-001",
  "agent": "InvestmentAgent",
  "status": "success",
  "result": {
    "enterprise_candidates": [...],
    "profiles": [...],
    "scores": [...],
    "recommendations": [...],
    "strategy": {...}
  },
  "trace": {
    "tools_used": ["enterprise_search_tool", "enterprise_scoring_tool"],
    "data_sources": ["enterprise", "enterprise_profile"],
    "execution_time_ms": 3200,
    "token_usage": 4500
  },
  "error": null,
  "completed_at": "2026-07-21T09:00:05Z"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | 是 | 对应请求的 task_id |
| agent | string | 是 | 执行 Agent 名称 |
| status | string | 是 | success / partial / failed |
| result | object | 是 | 业务结果数据 |
| trace | object | 是 | 执行追踪信息 |
| error | object | 否 | 错误详情（仅 status=failed 时） |
| completed_at | string | 是 | 完成时间戳 |

---

## 4. Agent 能力注册表

每个业务 Agent 必须向 Supervisor 注册以下信息：

```json
{
  "agent_name": "RiskAgent",
  "display_name": "企业风险预警智能体",
  "capability": [
    "risk_score",
    "risk_analysis",
    "risk_report",
    "batch_risk_scan",
    "risk_trend"
  ],
  "input_schema": {
    "enterprise_id": "string",
    "analysis_type": "string"
  },
  "output_schema": {
    "risk_score": "number",
    "risk_level": "string",
    "risk_factors": "array",
    "recommendation": "string"
  },
  "dependencies": ["DatabaseAgent"],
  "consumers": ["Supervisor", "BIAgent"],
  "tools_required": [
    "enterprise_query_tool",
    "risk_indicator_tool",
    "risk_scoring_tool"
  ]
}
```

---

## 5. 12 个 Agent 完整能力清单

### 01 — 总架构师 Agent
- **角色**：Chief AI Architect
- **负责**：总体架构审核、技术路线、架构一致性检查
- **能力**：architecture_review, design_audit, tech_decision
- **输入**：设计文档
- **输出**：审核意见
- **依赖**：无
- **消费者**：所有 Agent

### 02 — Supervisor Agent
- **角色**：AI 产业运营总经理
- **负责**：意图识别、任务规划、Agent 路由、结果聚合、Trace 管理
- **能力**：intent_recognition, task_planning, agent_routing, result_aggregation, trace_management
- **输入**：User Query
- **输出**：Final Response
- **依赖**：DatabaseAgent
- **消费者**：Frontend, All Business Agents

### 03 — Investment Agent (招商)
- **角色**：AI 招商经理
- **负责**：企业搜索、企业画像、企业评分、招商推荐、招商策略
- **能力**：enterprise_search, enterprise_profile, enterprise_scoring, investment_recommend, investment_strategy
- **输入**：行业、区域、招商目标
- **输出**：企业列表、画像、评分、推荐、策略报告
- **依赖**：DatabaseAgent, IndustryAgent, PolicyAgent, RiskAgent
- **消费者**：Supervisor, BIAgent

### 04 — Policy RAG Agent (政策)
- **角色**：AI 政策顾问
- **负责**：政策采集、RAG 检索、政策匹配、政策推荐
- **能力**：policy_search, policy_match, policy_recommend, policy_analysis
- **输入**：企业画像 / 政策查询
- **输出**：匹配政策列表、匹配度、申请条件、材料清单
- **依赖**：DatabaseAgent
- **消费者**：Supervisor, InvestmentAgent, EnterpriseServiceAgent, BIAgent

### 05 — Enterprise Service Agent (企业服务)
- **角色**：AI 企业管家
- **负责**：需求理解、服务分类、工单管理、流程自动化、生命周期管理
- **能力**：service_intent_analysis, service_classification, ticket_management, service_workflow, lifecycle_management
- **输入**：企业需求描述
- **输出**：服务方案、工单、流程状态
- **依赖**：PolicyAgent, IndustryAgent, RiskAgent
- **消费者**：Supervisor, BIAgent

### 06 — Industry Agent (产业分析)
- **角色**：AI 产业研究院
- **负责**：产业链分析、知识图谱、趋势预测、市场分析、招商方向推荐
- **能力**：industry_chain_analysis, industry_trend, market_analysis, investment_direction, knowledge_graph_query
- **输入**：产业名称、分析维度
- **输出**：产业链结构、趋势评分、市场报告、招商方向
- **依赖**：DatabaseAgent
- **消费者**：Supervisor, InvestmentAgent, BIAgent

### 07 — Risk Agent (风险预警)
- **角色**：企业风险雷达
- **负责**：风险评分、舆情分析、异常检测、风险预警
- **能力**：risk_score, risk_analysis, risk_report, batch_risk_scan, risk_trend
- **输入**：企业 ID / 行业
- **输出**：风险评分 0-100、风险等级、风险因素、建议
- **依赖**：DatabaseAgent
- **消费者**：Supervisor, InvestmentAgent, EnterpriseServiceAgent, BIAgent

### 08 — BI Agent (驾驶舱)
- **角色**：AI 数字驾驶舱
- **负责**：KPI 体系、数据分析、Dashboard、ECharts、AI 洞察
- **能力**：kpi_query, dashboard_data, chart_generation, ai_insight, data_analysis
- **输入**：指标查询 / 分析主题
- **输出**：KPI JSON、ECharts Option、洞察报告
- **依赖**：所有业务 Agent（通过 Supervisor）
- **消费者**：Supervisor, Frontend

### 09 — Database Agent (数据库)
- **角色**：数据底座
- **负责**：PostgreSQL/pgvector/Redis 架构、数据模型、Memory 存储、ORM
- **能力**：data_query, vector_search, memory_save, memory_search, schema_management
- **输入**：数据请求（通过 Tool Gateway）
- **输出**：数据结果
- **依赖**：无（基础设施层）
- **消费者**：所有 Agent（通过 Tool Gateway）

### 10 — FastAPI Backend Agent (后端)
- **角色**：后端平台
- **负责**：API Gateway、Agent Runtime、LangGraph 集成、WebSocket、JWT/RBAC
- **能力**：api_gateway, agent_runtime, workflow_execution, websocket_event, auth
- **输入**：HTTP/WS 请求
- **输出**：HTTP/WS 响应
- **依赖**：SupervisorAgent, DatabaseAgent
- **消费者**：React Frontend

### 11 — React Frontend Agent (前端)
- **角色**：用户交互层
- **负责**：AI Chat UI、Agent Trace UI、Dashboard、GIS、企业画像
- **能力**：chat_ui, trace_visualization, dashboard_render, enterprise_view, gis_map
- **输入**：API 数据
- **输出**：UI 渲染
- **依赖**：FastAPI Backend
- **消费者**：End User

### 12 — Demo/Product Agent (产品)
- **角色**：产品负责人
- **负责**：比赛策略、Demo 设计、商业方案、产品路线图
- **能力**：demo_design, pitch_strategy, business_model, product_roadmap
- **输入**：项目状态
- **输出**：产品文档、Demo 脚本、商业方案
- **依赖**：所有 Agent
- **消费者**：比赛评委、客户

---

## 6. Intent 分类体系（Supervisor 路由依据）

| Intent | 路由目标 | 说明 |
|--------|---------|------|
| investment_search | InvestmentAgent | 企业搜索 |
| investment_profile | InvestmentAgent | 企业画像 |
| investment_scoring | InvestmentAgent | 企业评分 |
| investment_strategy | InvestmentAgent | 招商策略 |
| policy_query | PolicyAgent | 政策查询 |
| policy_match | PolicyAgent | 政策匹配 |
| policy_recommend | PolicyAgent | 政策推荐 |
| service_request | EnterpriseServiceAgent | 企业服务 |
| service_ticket | EnterpriseServiceAgent | 工单管理 |
| industry_analysis | IndustryAgent | 产业分析 |
| industry_trend | IndustryAgent | 趋势分析 |
| industry_chain | IndustryAgent | 产业链分析 |
| risk_single | RiskAgent | 单企业风险 |
| risk_batch | RiskAgent | 批量风险扫描 |
| risk_trend | RiskAgent | 风险趋势 |
| dashboard_kpi | BIAgent | KPI 查询 |
| dashboard_chart | BIAgent | 图表数据 |
| ai_insight | BIAgent | AI 洞察 |
| compound | Supervisor | 复合任务（多 Agent 协作） |

---

## 7. 错误处理协议

### Agent 执行失败
```
Attempt 1 (原 Agent)
  ↓ 失败
Attempt 2 (同 Agent 重试)
  ↓ 失败
Fallback (降级策略)
  ↓ 失败
Human Review (人工介入)
```

### 错误返回格式
```json
{
  "task_id": "TASK-001",
  "agent": "InvestmentAgent",
  "status": "failed",
  "result": null,
  "error": {
    "code": "DATA_UNAVAILABLE",
    "message": "企业数据暂不可用",
    "detail": "enterprise_profile 表连接超时",
    "retry_count": 2,
    "fallback_used": "cached_profile"
  },
  "trace": {...}
}
```

### 错误码定义

| 错误码 | 类型 | 重试 | 说明 |
|--------|------|------|------|
| DATA_UNAVAILABLE | 数据层 | 是 | 数据暂时不可用 |
| LLM_TIMEOUT | 智能层 | 是 | LLM 超时 |
| AGENT_TIMEOUT | Agent层 | 是 | Agent 执行超时 |
| INVALID_INPUT | 输入层 | 否 | 输入参数非法 |
| PERMISSION_DENIED | 安全层 | 否 | 权限不足 |
| TOOL_ERROR | 工具层 | 是 | 工具执行异常 |
| UNKNOWN | 未知 | 是 | 未知错误 |

---

## 8. Agent Trace 规范

每次执行必须记录完整链路：

```
User Request
  ↓
Supervisor Decision (intent, plan)
  ↓
Agent Call (agent_name, input)
  ↓
Tool Call (tool_name, parameters)
  ↓
Data Source (table, query)
  ↓
Tool Result (output, duration)
  ↓
Agent Result (status, output)
  ↓
Final Response (aggregated)
```

### Trace 数据模型
```json
{
  "trace_id": "TRACE-001",
  "task_id": "TASK-001",
  "steps": [
    {
      "step": 1,
      "type": "supervisor_decision",
      "agent": "Supervisor",
      "action": "intent_recognition",
      "input": {"query": "..."},
      "output": {"intent": "compound", "plan": [...]},
      "timestamp": "2026-07-21T09:00:00Z"
    },
    {
      "step": 2,
      "type": "agent_call",
      "agent": "IndustryAgent",
      "action": "industry_analysis",
      "input": {"industry": "robot"},
      "output": {"trend_score": 85},
      "tools_used": ["industry_search_tool"],
      "timestamp": "2026-07-21T09:00:02Z"
    }
  ]
}
```

---

## 9. 禁止事项清单（不可违反）

1. ❌ 业务 Agent 直接调用其他业务 Agent
2. ❌ 任何 Agent 直接访问数据库
3. ❌ 绕过 Supervisor Tool Gateway
4. ❌ 新增第二个 Supervisor
5. ❌ 单 Agent Chatbot 模式
6. ❌ 绕过 LangGraph Workflow
7. ❌ 修改总体五层架构
8. ❌ Trace 链路不完整

---

## 10. 版本兼容性

- 本协议 V1.0 适用于 Industrial Park Agent MVP 阶段
- 所有 Agent 的 input_schema 和 output_schema 可扩展但不可删减已有字段
- capability 列表可追加，不可移除已有能力
- 任何 schema 变更需要总架构师 Agent 审核

---

**文档状态：FROZEN V1.0**
**下一文档：Supervisor Agent Technical Implementation Design V1.1**
