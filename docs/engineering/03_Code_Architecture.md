# Industrial Park Agent — 代码架构

## 分层架构

```
React Frontend (14 .tsx)
    ↓ HTTP/WebSocket
FastAPI Gateway (12 endpoints)
    ↓
LangGraph Supervisor (7 nodes)
    ↓
6 Business Agent Graphs (4-7 nodes each)
    ↓
Tool Gateway (14 tools, 5 categories)
    ↓
PostgreSQL + pgvector + Redis
```

## 模块依赖图

```
app/main.py
  ├── app/config.py
  ├── app/api/v1/
  │   ├── agent.py      → app.langgraph.graph
  │   ├── business.py    → app.langgraph.graphs/*
  │   ├── task.py        → app.agents.registry
  │   ├── trace.py
  │   ├── auth.py        → app.core.security
  │   ├── dashboard.py
  │   └── health.py
  ├── app/core/
  │   ├── llm_gateway.py  (GPT-4o → Claude → DeepSeek)
  │   ├── security.py     (JWT)
  │   └── logger.py
  ├── app/database/
  │   ├── session.py
  │   └── models/         (9 ORM models)
  ├── app/langgraph/
  │   ├── graph.py        (Supervisor StateGraph)
  │   ├── state.py        (SupervisorState TypedDict)
  │   ├── nodes/
  │   │   ├── supervisor_nodes.py  (7 nodes, LLM-driven)
  │   │   ├── investment_nodes.py  (7 nodes)
  │   │   ├── risk_nodes.py        (6 nodes + prediction)
  │   │   ├── policy_nodes.py      (7 nodes, RAG)
  │   │   ├── industry_nodes.py    (6 nodes)
  │   │   ├── service_nodes.py     (4 nodes)
  │   │   └── bi_nodes.py          (4 nodes)
  │   └── graphs/
  │       └── investment_graph.py
  ├── app/agents/
  │   └── registry.py    (6 agents registered)
  └── app/tools/
      └── gateway.py      (14 tools, permission matrix)
```

## 所有 Agent 实现状态

| Agent | Nodes | Graph | Status |
|-------|:---:|:---:|:---:|
| Supervisor | 7 | ✅ graph.py | LLM Gateway 驱动 |
| Investment | 7 | ✅ investment_graph.py | 完整 Pipeline |
| Risk | 6+1 | ⏳ (inline) | 含预测模型 |
| Policy RAG | 7 | ⏳ (inline) | RAG Pipeline |
| Industry | 6 | ✅ inline | 产业链分析 |
| Service | 4 | ✅ inline | 工单系统 |
| BI | 4 | ✅ inline | KPI计算 |
