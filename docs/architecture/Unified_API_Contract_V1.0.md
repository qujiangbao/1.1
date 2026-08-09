# Industrial Park Agent
# Unified API Contract V1.0

> 版本：V1.0 | 状态：FROZEN
> 
> 本文档定义 FastAPI Backend 和 React Frontend 之间的全部 API 契约。
> Backend Agent 和 Frontend Agent 必须严格遵守本协议。

---

## 1. API 总览

| 类别 | 方法 | 路径 | 说明 |
|------|------|------|------|
| Agent Chat | POST | /api/v1/agent/chat | 用户对话入口（核心） |
| Agent Task | POST | /api/v1/agent/task | 创建 Agent 任务 |
| Task Status | GET | /api/v1/agent/task/{task_id} | 查询任务状态 |
| Task Trace | GET | /api/v1/agent/task/{task_id}/trace | 查询执行链路 |
| Agent Status | GET | /api/v1/agent/status | Agent 系统状态 |
| Enterprise | GET | /api/v1/enterprise/{id} | 企业详情 |
| Enterprise | GET | /api/v1/enterprise/search | 企业搜索 |
| Investment | POST | /api/v1/investment/search | 招商搜索 |
| Investment | GET | /api/v1/investment/profile/{id} | 企业招商画像 |
| Investment | POST | /api/v1/investment/scoring | 企业评分 |
| Investment | POST | /api/v1/investment/recommend | 招商推荐 |
| Investment | POST | /api/v1/investment/strategy | 招商策略 |
| Policy | POST | /api/v1/policy/match | 政策匹配 |
| Policy | POST | /api/v1/policy/search | 政策搜索 |
| Risk | POST | /api/v1/risk/analyze | 企业风险分析 |
| Risk | POST | /api/v1/risk/batch | 批量风险扫描 |
| Risk | GET | /api/v1/risk/trend/{enterprise_id} | 风险趋势 |
| Industry | POST | /api/v1/industry/analyze | 产业分析 |
| Industry | GET | /api/v1/industry/{id}/chain | 产业链查询 |
| Industry | POST | /api/v1/industry/trend | 趋势分析 |
| Service | POST | /api/v1/service/request | 企业服务请求 |
| Service | GET | /api/v1/service/ticket/{id} | 服务工单 |
| Dashboard | GET | /api/v1/dashboard/overview | 总览数据 |
| Dashboard | GET | /api/v1/dashboard/kpi | KPI 数据 |
| Dashboard | GET | /api/v1/dashboard/chart/{id} | 图表数据 |
| Dashboard | POST | /api/v1/dashboard/insight | AI 洞察 |
| Auth | POST | /api/v1/auth/login | 登录 |
| Auth | POST | /api/v1/auth/refresh | 刷新 Token |
| WebSocket | WS | /api/v1/ws/task/{task_id} | 实时事件流 |
| Health | GET | /api/v1/health | 健康检查 |

---

## 2. 通用规范

### 2.1 认证

所有 API 需要 JWT Bearer Token（除 login 和 health）：

```
Authorization: Bearer <jwt_token>
```

### 2.2 通用响应格式

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "request_id": "REQ-001",
    "timestamp": "2026-07-21T09:00:00Z",
    "execution_time_ms": 350
  }
}
```

### 2.3 错误响应格式

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_INPUT",
    "message": "参数 industry 不能为空",
    "detail": "industry field is required"
  },
  "meta": {
    "request_id": "REQ-001",
    "timestamp": "2026-07-21T09:00:00Z"
  }
}
```

### 2.4 分页

```json
// 请求
GET /api/v1/enterprise/search?keyword=robot&page=1&page_size=20

// 响应
{
  "success": true,
  "data": {
    "items": [...],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 156,
      "total_pages": 8
    }
  }
}
```

---

## 3. 核心 API 详细定义

### 3.1 Agent Chat（用户对话入口）

```
POST /api/v1/agent/chat
```

**请求**：
```json
{
  "conversation_id": "CONV-001",
  "message": "帮我寻找广州机器人产业链企业并评估风险",
  "context": {
    "park_id": "P001",
    "user_role": "investment_manager"
  }
}
```

**响应**（同步模式）：
```json
{
  "success": true,
  "data": {
    "task_id": "TASK-20260721-001",
    "conversation_id": "CONV-001",
    "status": "completed",
    "response": "## 广州机器人产业招商分析\n\n### 产业趋势\n...",
    "agents_used": ["IndustryAgent", "InvestmentAgent", "RiskAgent"],
    "trace_id": "TRACE-001",
    "execution_time_ms": 8500
  }
}
```

**响应**（流式模式，通过 WebSocket）：
```
WS /api/v1/ws/task/{task_id}

事件流:
→ {"type": "task_started", "task_id": "TASK-001"}
→ {"type": "agent_started", "agent": "IndustryAgent", "message": "正在分析机器人产业趋势..."}
→ {"type": "agent_progress", "agent": "IndustryAgent", "progress": 0.5}
→ {"type": "agent_completed", "agent": "IndustryAgent", "result": {...}}
→ {"type": "agent_started", "agent": "InvestmentAgent", "message": "正在搜索产业链企业..."}
→ {"type": "agent_completed", "agent": "InvestmentAgent", "result": {...}}
→ {"type": "task_completed", "task_id": "TASK-001", "response": "..."}
```

### 3.2 Task Trace

```
GET /api/v1/agent/task/{task_id}/trace
```

**响应**：
```json
{
  "success": true,
  "data": {
    "trace_id": "TRACE-001",
    "task_id": "TASK-001",
    "status": "completed",
    "started_at": "2026-07-21T09:00:00Z",
    "completed_at": "2026-07-21T09:00:08Z",
    "execution_time_ms": 8500,
    "steps": [
      {
        "step": 1,
        "type": "supervisor_decision",
        "agent": "Supervisor",
        "action": "intent_recognition",
        "input": {"query": "..."},
        "output": {"intent": "compound", "plan": ["industry", "investment", "risk"]},
        "timestamp": "2026-07-21T09:00:00.100Z",
        "duration_ms": 450
      },
      {
        "step": 2,
        "type": "agent_call",
        "agent": "IndustryAgent",
        "action": "industry_analysis",
        "input": {"industry": "robot"},
        "output": {"trend_score": 85, "chain": [...]},
        "tools_used": ["industry_vector_search", "knowledge_graph_query"],
        "timestamp": "2026-07-21T09:00:01.000Z",
        "duration_ms": 2500
      }
    ],
    "nodes": [
      {"id": "supervisor", "label": "Supervisor", "type": "supervisor"},
      {"id": "industry", "label": "IndustryAgent", "type": "agent"},
      {"id": "investment", "label": "InvestmentAgent", "type": "agent"},
      {"id": "risk", "label": "RiskAgent", "type": "agent"}
    ],
    "edges": [
      {"from": "supervisor", "to": "industry"},
      {"from": "industry", "to": "investment"},
      {"from": "investment", "to": "risk"},
      {"from": "risk", "to": "supervisor"}
    ]
  }
}
```

---

## 4. 业务 API 详细定义

### 4.1 招商 API

#### 企业搜索
```
POST /api/v1/investment/search
```
```json
// 请求
{
  "keyword": "机器人",
  "industry": "robotics",
  "region": "guangzhou",
  "limit": 20
}

// 响应
{
  "success": true,
  "data": {
    "enterprises": [
      {
        "enterprise_id": "10001",
        "name": "广州智行机器人有限公司",
        "industry": "机器人",
        "sub_industry": "工业机器人",
        "location": "广州黄埔区",
        "brief": "专注于工业机器人研发制造...",
        "score": 92,
        "score_level": "STRONG_MATCH"
      }
    ],
    "total": 45
  }
}
```

#### 企业招商画像
```
GET /api/v1/investment/profile/{enterprise_id}
```
```json
{
  "success": true,
  "data": {
    "enterprise_id": "10001",
    "name": "广州智行机器人有限公司",
    "basic": {
      "industry": "机器人",
      "location": "广州黄埔区",
      "established": "2018",
      "employee_count": 250
    },
    "technology": {
      "core_product": "六轴工业机器人",
      "tech_stack": ["ROS", "OpenCV", "PyTorch"],
      "patents": 15,
      "tech_score": 88
    },
    "growth": {
      "revenue_growth": "35%",
      "employee_growth": "20%",
      "growth_score": 85
    },
    "finance": {
      "funding_stage": "B轮",
      "total_funding": "2亿",
      "capital_score": 78
    },
    "investment_score": 92,
    "recommendation": "强烈推荐引入园区"
  }
}
```

### 4.2 政策 API

#### 政策匹配
```
POST /api/v1/policy/match
```
```json
// 请求
{
  "enterprise_id": "10001",
  "requirement": "研发补贴"
}

// 响应
{
  "success": true,
  "data": {
    "enterprise_id": "10001",
    "policies": [
      {
        "policy_id": "POL-001",
        "title": "广州市人工智能产业扶持办法",
        "level": "municipal",
        "match_score": 95,
        "match_reasons": ["行业匹配: 机器人", "区域匹配: 广州", "研发投入达标"],
        "subsidy_range": "100-500万",
        "requirements": [
          "注册地在广州",
          "研发投入占比 > 5%",
          "拥有核心技术专利"
        ],
        "materials": [
          "企业营业执照",
          "研发投入证明",
          "专利证书"
        ],
        "deadline": "2026-09-30",
        "department": "广州市工信局"
      }
    ],
    "total_matched": 8
  }
}
```

### 4.3 风险 API

#### 企业风险分析
```
POST /api/v1/risk/analyze
```
```json
// 请求
{"enterprise_id": "10001"}

// 响应
{
  "success": true,
  "data": {
    "enterprise_id": "10001",
    "enterprise_name": "广州智行机器人有限公司",
    "risk_score": 28,
    "risk_level": "LOW",
    "risk_factors": [
      {"type": "business", "score": 15, "reason": "经营正常，增长稳定"},
      {"type": "finance", "score": 30, "reason": "B轮融资正常，现金流健康"},
      {"type": "public_opinion", "score": 20, "reason": "无负面舆情"},
      {"type": "legal", "score": 10, "reason": "无法律纠纷"},
      {"type": "talent", "score": 25, "reason": "招聘活跃，团队稳定"},
      {"type": "market", "score": 35, "reason": "行业竞争加剧"}
    ],
    "recommendation": "企业经营稳定，建议正常关注",
    "trend": "stable"
  }
}
```

### 4.4 产业分析 API

```
POST /api/v1/industry/analyze
```
```json
// 请求
{
  "industry": "机器人",
  "region": "广州",
  "analysis_type": "full"
}

// 响应
{
  "success": true,
  "data": {
    "industry": "机器人",
    "trend_score": 85,
    "trend_level": "STRATEGIC",
    "chain": {
      "upstream": ["传感器", "伺服电机", "控制器"],
      "midstream": ["工业机器人", "服务机器人", "特种机器人"],
      "downstream": ["汽车制造", "3C电子", "医疗"]
    },
    "market": {
      "tam": "5000亿（全国）",
      "growth_rate": "25%",
      "competition": "中等"
    },
    "guangzhou_status": {
      "enterprise_count": 320,
      "chain_completeness": "75%",
      "gap": ["高端传感器", "精密减速器"],
      "advantage": ["系统集成", "应用场景丰富"]
    },
    "investment_direction": [
      {"direction": "核心零部件", "priority": "HIGH", "reason": "产业链缺口"},
      {"direction": "人形机器人", "priority": "MEDIUM", "reason": "未来趋势"},
      {"direction": "AI+机器人", "priority": "HIGH", "reason": "技术融合"}
    ]
  }
}
```

### 4.5 企业服务 API

```
POST /api/v1/service/request
```
```json
// 请求
{
  "enterprise_id": "10001",
  "request": "我们需要申请研发补贴，并寻找产业链合作伙伴",
  "priority": "high"
}

// 响应
{
  "success": true,
  "data": {
    "ticket_id": "ST-001",
    "status": "processing",
    "intent_analysis": {
      "primary": "policy_application",
      "secondary": "partner_matching"
    },
    "assigned_services": [
      {"service": "policy_service", "agent": "PolicyAgent", "status": "pending"},
      {"service": "matchmaking", "agent": "IndustryAgent", "status": "pending"}
    ],
    "estimated_time": "30秒"
  }
}
```

### 4.6 BI Dashboard API

#### 总览
```
GET /api/v1/dashboard/overview
```
```json
{
  "success": true,
  "data": {
    "park_overview": {
      "total_enterprises": 12580,
      "new_this_month": 45,
      "growth_rate": "3.2%",
      "active_rate": "92%"
    },
    "investment": {
      "opportunities": 230,
      "in_negotiation": 45,
      "signed": 12,
      "conversion_rate": "5.2%"
    },
    "risk": {
      "high_risk": 20,
      "medium_risk": 80,
      "low_risk": 500,
      "risk_trend": " improving"
    },
    "ai_operations": {
      "agent_calls_today": 1520,
      "tasks_completed": 1480,
      "success_rate": "97.4%",
      "avg_response_time_ms": 3200
    }
  }
}
```

---

## 5. WebSocket 事件协议

### 连接
```
ws://host:port/api/v1/ws/task/{task_id}
需要 JWT Token 作为 query param: ?token=<jwt>
```

### 事件类型

| 事件 | 说明 | Payload |
|------|------|---------|
| task_started | 任务开始 | {task_id, intent, plan} |
| task_completed | 任务完成 | {task_id, response, trace_id} |
| task_failed | 任务失败 | {task_id, error} |
| agent_started | Agent 开始 | {agent, action, message} |
| agent_progress | Agent 进度 | {agent, progress: 0.0-1.0} |
| agent_completed | Agent 完成 | {agent, result} |
| agent_failed | Agent 失败 | {agent, error} |
| tool_call | 工具调用 | {agent, tool, params} |
| tool_result | 工具结果 | {agent, tool, result} |
| streaming_text | LLM 流式输出 | {agent, text_delta} |
| heartbeat | 心跳 | {timestamp} |

---

## 6. 权限与角色

### 角色定义

| 角色 | 权限 |
|------|------|
| admin | 全部 API 访问 + 系统管理 |
| park_manager | 招商、风险、产业、Dashboard、企业服务 |
| investment_manager | 招商相关 API |
| policy_manager | 政策相关 API |
| viewer | 只读 Dashboard |

### 权限矩阵

| API | admin | park_manager | investment | policy | viewer |
|-----|:-----:|:-----:|:-----:|:-----:|:-----:|
| agent/chat | ✓ | ✓ | ✓ | ✓ | ✓ |
| agent/task | ✓ | ✓ | | | |
| agent/task/trace | ✓ | ✓ | ✓ | ✓ | ✓ |
| investment/* | ✓ | ✓ | ✓ | | |
| policy/* | ✓ | ✓ | | ✓ | |
| risk/* | ✓ | ✓ | | | |
| industry/* | ✓ | ✓ | ✓ | | |
| service/* | ✓ | ✓ | | | |
| dashboard/* | ✓ | ✓ | ✓ | ✓ | ✓ |
| auth/* | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## 7. 提供给 Backend Agent 的实现要求

1. **FastAPI 路由结构**：按 `/api/v1/<domain>/<action>` 组织
2. **Pydantic Schema**：每个 API 的 Request/Response 必须有 Pydantic 模型
3. **Middleware**：JWT → RBAC → Logging → CORS
4. **Async**：所有数据库操作使用 SQLAlchemy Async
5. **WebSocket**：使用 FastAPI WebSocket + Redis Pub/Sub 广播 Agent 事件
6. **Docker**：提供 Dockerfile + docker-compose.yml

---

## 8. 提供给 Frontend Agent 的消费要求

1. **API Client**：封装 `api/agent.api.ts`、`api/dashboard.api.ts` 等模块
2. **WebSocket Hook**：`useAgentTask(taskId)` → 返回实时事件流
3. **Trace 可视化**：用 React Flow 渲染 nodes/edges
4. **Chart**：用 ECharts 渲染图表数据
5. **流式文本**：用 StreamingText 组件展示 LLM 逐字输出

---

**文档状态：FROZEN V1.0**
**下一阶段：逐个 Agent LangGraph Workflow 设计**
