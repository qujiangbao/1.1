# Industrial Park Agent — Architecture (FROZEN)

> **Single Source of Truth** | 版本：V1.3 | 状态：FROZEN
> 
> 本文档是 Industrial Park Agent 架构的**唯一事实来源**。
> 任何架构变更必须先更新本文档，再修改代码。

---

## 1. 系统架构全景

```
                    User / Browser
                         |
                  Nginx :80 (reverse proxy)
                    /        \
                   /          \
        Next.js :3000       FastAPI :8000
        (Ant Design)        (API Gateway)
                                 |
                    LangGraph Supervisor (7 nodes)
                   /    |    |    |    |    \
                  /     |    |    |    |     \
           Industry Investment Risk Policy Service  BI
           Agent    Agent    Agent Agent  Agent   Agent
                  \     |    |    |    |    /
                   \    |    |    |    |   /
                    Tool Gateway (18 tools)
                           |
              PostgreSQL 16 + pgvector + Redis 7
```

## 2. 核心架构原则（FROZEN）

| # | 原则 | 说明 |
|---|------|------|
| 1 | **Supervisor 唯一调度** | 业务 Agent 禁止直接调用，所有通信必须经过 Supervisor |
| 2 | **单一职责** | 每个 Agent 只负责一个业务领域 |
| 3 | **全链路可追踪** | 每次执行记录完整的 Agent Trace |
| 4 | **数据经 Tool Gateway** | 禁止 Agent 直连数据库，所有数据访问经过 Tool Gateway |
| 5 | **Agent 接口不可变** | `execute_business_agent(agent_name, task, state)` 签名永久冻结 |
| 6 | **Supervisor 7 节点不变** | 只能在现有节点内部添加 hooks/filters，不可增删节点 |

## 3. 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| AI 编排 | LangGraph (StateGraph) | >=0.2.0 |
| 后端 | FastAPI (Python 3.12) | >=0.115 |
| 前端 | Next.js 16 + React + Ant Design | 16.x |
| 数据库 | PostgreSQL + pgvector | 16 / 0.8.5 |
| 缓存 | Redis | 7.x |
| 向量检索 | pgvector (HNSW) | 0.8.5 |
| 部署 | Docker Compose | — |
| LLM | DeepSeek V4 | — |

## 4. Agent 架构

### 4.1 Supervisor Agent（AI 运营总经理）

```
User Input → Intent Recognition → Task Planning → Agent Routing → Result Aggregation
```

7 个固定节点：Industry → Investment → Risk → Policy → Service → BI → Aggregator

### 4.2 6 个业务 Agent

| Agent | 职责 | 文档 |
|-------|------|------|
| **Industry Agent** | 产业链分析、趋势预测、招商方向 | `docs/agents/Industry_Agent_Technical_Design_V1.0.md` |
| **Investment Agent** | 企业搜索→画像→评分→推荐→策略 | `docs/agents/Investment_Agent_Workflow_V1.0.md` |
| **Risk Agent** | 6 维风险评分（经营/财务/舆情/法律/人才/市场） | `docs/agents/Risk_Agent_Workflow_V1.0.md` |
| **Policy Agent** | PDF 解析→向量检索→政策匹配→申报建议 | `docs/agents/Policy_RAG_Workflow_V1.0.md` |
| **Enterprise Service Agent** | 需求理解→服务分类→工单管理→流程自动化 | `docs/agents/Enterprise_Service_Architecture_V1.0.md` |
| **BI Agent** | 5 大维度 30+ KPI，ECharts 可视化，AI 洞察 | `docs/agents/BI_Agent_Architecture_V1.0.md` |

## 5. 数据架构

```
Policy Pipeline:
  gz.gov.cn → Crawl4AI (offline) → Markdown cache → PolicyRetriever
    → KnowledgeTool → pgvector (HNSW) → PolicyAgent

Enterprise Pipeline:
  天眼查/企查查 → Enterprise Data Adapters → PostgreSQL
    → EnterpriseTool → InvestmentAgent/RiskAgent

Database (17 tables, frozen):
  business (7) + runtime (5) + rbac (5)
```

## 6. 部署架构

```
Docker Compose:
  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌───────┐
  │  Nginx  │  │ FastAPI  │  │ PostgreSQL│  │ Redis │
  │  :80    │→ │  :8000   │→ │  :5432   │  │:6379  │
  └─────────┘  └─────────┘  └──────────┘  └───────┘

Windows PowerShell: Next.js :3000
WSL/Linux: FastAPI :8000 + PostgreSQL + Redis
```

## 7. 版本历史

| 版本 | 日期 | 状态 | 说明 |
|------|------|:---:|------|
| V1.0 | 2026-07-21 | ARCHIVE | 12 Agent 架构设计完成 |
| V1.1 | 2026-07-22 | FREEZE | 比赛金奖版（main 分支永久冻结） |
| V1.2 | 2026-07-25 | — | 生产升级（P0-P8 全部完成） |
| V1.3 | 2026-07-28 | CURRENT | Crawl4AI 政策集成 + 生产稳定 |

## 8. 文档导航

| 目录 | 用途 |
|------|------|
| `docs/ARCHITECTURE.md` | 本文档 — 架构唯一事实来源 |
| `docs/architecture/` | 冻结设计规范（通信协议、API 契约、数据库 DDL） |
| `docs/agents/` | 各 Agent 详细设计文档 |
| `docs/engineering/` | 工程实施文档（实现报告、升级记录、runbook） |
| `docs/archive/` | 历史版本归档（v1.0 草稿、v1.1 比赛文档） |
| `docs/doc-index.md` | 完整文档索引 |
| `docs/agent-index.md` | Agent 职责与文档索引 |
| `CODEBUDDY.md` | AI 开发助手指南 |
| `README.md` | 项目概览 + 快速启动 |

---

**文档结束。架构变更必须通过 PR 并更新本文档。**
