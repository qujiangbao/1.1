# Industrial Park Agent MVP Implementation Plan V1.0

> 版本：V1.0 | 日期：2026-07-21 | 工期：10-15 天

---

## 一、Git Repository Structure

```
industrial-park-agent/
  |
  ├── README.md
  ├── docker-compose.yml
  ├── .env.example
  ├── Makefile                          # 常用命令快捷方式
  |
  ├── docs/
  │   ├── engineering/                  # 工程文档
  │   │   ├── 01_Engineering_Readiness.md
  │   │   ├── 02_Implementation_Plan.md  ← 本文档
  │   │   ├── 03_Code_Architecture.md
  │   │   ├── 04_API_Spec.md
  │   │   ├── 05_Test_Plan.md
  │   │   └── 06_Deployment_Guide.md
  │   └── design/                       # 设计文档（已有 15+ 份）
  │
  ├── backend/
  │   ├── app/
  │   │   ├── main.py                   ✅
  │   │   ├── config.py                 ✅
  │   │   ├── api/v1/                   # API 路由
  │   │   │   ├── agent.py              ✅
  │   │   │   ├── task.py               ✅
  │   │   │   ├── trace.py              ✅
  │   │   │   ├── dashboard.py          ✅
  │   │   │   ├── auth.py               ✅
  │   │   │   ├── health.py             ✅
  │   │   │   ├── investment.py         ⏳
  │   │   │   ├── policy.py             ⏳
  │   │   │   ├── risk.py               ⏳
  │   │   │   ├── industry.py           ⏳
  │   │   │   └── service.py            ⏳
  │   │   ├── core/
  │   │   │   ├── security.py           ✅
  │   │   │   ├── logger.py             ✅
  │   │   │   └── llm_gateway.py        ⏳ V2.0 新增
  │   │   ├── database/
  │   │   │   ├── session.py            ✅
  │   │   │   └── models/               ⏳ SQLAlchemy Models
  │   │   ├── schemas/                  ✅
  │   │   ├── langgraph/
  │   │   │   ├── graph.py              ✅ Supervisor
  │   │   │   ├── state.py              ✅
  │   │   │   ├── nodes/
  │   │   │   │   ├── supervisor_nodes.py  ✅
  │   │   │   │   ├── investment_nodes.py  ⏳
  │   │   │   │   ├── risk_nodes.py        ⏳
  │   │   │   │   ├── policy_nodes.py      ⏳
  │   │   │   │   ├── industry_nodes.py    ⏳
  │   │   │   │   ├── service_nodes.py     ⏳
  │   │   │   │   └── bi_nodes.py          ⏳
  │   │   │   └── graphs/
  │   │   │       ├── investment_graph.py  ⏳
  │   │   │       ├── risk_graph.py        ⏳
  │   │   │       └── ...
  │   │   ├── agents/
  │   │   │   └── registry.py           ✅
  │   │   └── tools/
  │   │       ├── gateway.py            ⏳
  │   │       ├── data_tools.py         ⏳
  │   │       └── knowledge_tools.py    ⏳
  │   ├── alembic/                      ⏳
  │   ├── tests/                        ⏳
  │   ├── Dockerfile                    ✅
  │   └── requirements.txt              ✅
  │
  └── frontend/
      ├── src/
      │   ├── app/                      # Next.js App Router
      │   ├── components/               # React 组件
      │   ├── api/                      ✅ client.ts
      │   ├── hooks/                    ⏳
      │   ├── store/                    ✅ chatStore.ts
      │   └── types/                    ✅ agent.ts
      ├── package.json                  ✅
      ├── Dockerfile                    ✅
      └── next.config.js                ✅
```

---

## 二、Sprint 0：基础设施（Day 1-2）

### 目标
可一键启动的开发环境

### 任务清单

| # | 任务 | 文件 | 验收标准 |
|---|------|------|---------|
| 0.1 | docker-compose 启动 PG + pgvector + Redis | docker-compose.yml | `docker compose up -d db redis` 成功 |
| 0.2 | 初始化 pgvector 扩展 | alembic/versions/001_init.py | `CREATE EXTENSION vector` 成功 |
| 0.3 | Alembic 生成 migration | alembic/ | `alembic upgrade head` 建表成功 |
| 0.4 | SQLAlchemy Models | database/models/*.py | 20 张表 ORM 映射 |
| 0.5 | Demo 种子数据 | scripts/seed_demo.py | 50 企业 + 30 政策入库 |
| 0.6 | LLM Gateway 基础实现 | core/llm_gateway.py | GPT-4o 调用测试通过 |
| 0.7 | Makefile 常用命令 | Makefile | `make dev` 一键启动 |

### 验收

```bash
make dev          # 启动全部服务
curl :8000/health # → {"status":"healthy"}
```

---

## 三、Sprint 1：Supervisor Runtime（Day 3-4）

### 目标
Supervisor 可真实调度 LLM 和 Agent

### 任务清单

| # | 任务 | 说明 |
|---|------|------|
| 1.1 | 接入 LLM Gateway | intent_recognition_node 调用真实 LLM |
| 1.2 | Agent Router 真实调用 | agent_router_node 调用 Agent Graph 而非 mock |
| 1.3 | Tool Gateway 框架 | gateway.py 实现：权限 → 验证 → 执行 → Trace |
| 1.4 | Data Tools 实现 | enterprise_query, enterprise_search, enterprise_profile_get |
| 1.5 | WebSocket 事件流 | Agent 状态实时推送到前端 |
| 1.6 | Human Approval 节点 | 暂停-审批-继续 流程 |

### 验收

```bash
curl -X POST :8000/api/v1/agent/chat \
  -d '{"message":"帮我找机器人企业"}'
# → Supervisor → LLM → intent=investment_search → Agent Router → 返回结果
```

---

## 四、Sprint 2：核心 Agent（Day 5-7）

### 目标
3 个核心 Agent 完整运行

### Investment Agent

| # | 任务 |
|---|------|
| 2.1 | investment_graph.py — 7 节点 LangGraph 图 |
| 2.2 | investment_nodes.py — Intent Parser / Search / Profile / Scoring / Recommend / Strategy / Report |
| 2.3 | 接入 enterprise_search_tool 和 scoring_tool |
| 2.4 | /api/v1/investment/search 路由 |

### Risk Agent

| # | 任务 |
|---|------|
| 2.5 | risk_graph.py — 6 节点图 |
| 2.6 | risk_nodes.py — Validator / Data Request / Feature Extract / Scoring / Explain / Report |
| 2.7 | 6 维风险指标计算逻辑 |
| 2.8 | 预测模型 predict() 函数 |
| 2.9 | /api/v1/risk/analyze + /api/v1/risk/predict 路由 |

### Policy RAG Agent

| # | 任务 |
|---|------|
| 2.10 | policy_graph.py — 7 节点图 |
| 2.11 | policy_nodes.py — Query Analyzer / Enterprise Loader / Vector Search / Filter / Rerank / Match / Format |
| 2.12 | pgvector 政策向量检索 |
| 2.13 | /api/v1/policy/search + /api/v1/policy/match 路由 |

### 验收

```
输入："帮我寻找广州机器人产业链企业并评估风险"
  → Supervisor 意图识别（LLM）
  → IndustryAgent 产业分析
  → InvestmentAgent 企业搜索 + 评分 + 推荐
  → RiskAgent 6 维风险评估
  → PolicyAgent 政策匹配
  → 聚合报告
```

---

## 五、Sprint 3：扩展 Agent + Backend API（Day 8-9）

### Industry Agent

| # | 任务 |
|---|------|
| 3.1 | industry_graph.py + nodes |
| 3.2 | 产业链分析 + 趋势评分 + 知识图谱查询 |

### Enterprise Service Agent

| # | 任务 |
|---|------|
| 3.3 | service_graph.py + nodes |
| 3.4 | 工单系统 + 生命周期管理 |

### BI Agent

| # | 任务 |
|---|------|
| 3.5 | bi_graph.py + nodes |
| 3.6 | KPI 计算 + Dashboard 数据聚合 |

### API 补全

| # | 路由 |
|---|------|
| 3.7 | /api/v1/industry/analyze |
| 3.8 | /api/v1/service/request |
| 3.9 | /api/v1/dashboard/overview |

---

## 六、Sprint 4：Frontend（Day 10-12）

### 目标
3 个核心页面可交互

| # | 页面 | 组件 | 依赖 |
|---|------|------|------|
| 4.1 | AI Chat | ChatWindow + StreamingText + AgentProgress | WebSocket |
| 4.2 | Agent Trace | ReactFlow + TraceNode + Timeline | /trace API |
| 4.3 | Dashboard | KPICard + LineChart + PieChart + GeoMap | /dashboard API |
| 4.4 | Enterprise Profile | 企业360画像 + 评分仪表盘 | /investment/profile |
| 4.5 | Human Approval UI | 审批弹窗 | WebSocket |

---

## 七、Sprint 5：Demo 打磨（Day 13-15）

| # | 任务 |
|---|------|
| 5.1 | Demo 数据预加载脚本 |
| 5.2 | 5 分钟演示脚本彩排 |
| 5.3 | 错误处理 + 降级逻辑 |
| 5.4 | 压力测试（10 并发） |
| 5.5 | Docker 一键部署验证 |
| 5.6 | README + 部署文档 |

---

## 八、测试计划

| 层级 | 工具 | 范围 |
|------|------|------|
| 单元测试 | pytest + pytest-asyncio | 每个 Node 函数、Tool 函数 |
| 集成测试 | pytest + httpx | API 端点端到端 |
| LangGraph 测试 | LangGraph test utilities | 图执行正确性 |
| E2E | 手动 | 完整 Demo 流程 |

### 测试覆盖率目标

| 模块 | 目标 |
|------|:---:|
| Tool Gateway | 90% |
| LangGraph Nodes | 80% |
| API Routes | 70% |
| Frontend | 手动验收 |

---

## 九、部署计划

```yaml
# docker-compose.yml — 最终版本
services:
  db:        # PostgreSQL 16 + pgvector
  redis:     # Redis 7
  api:       # FastAPI :8000
  frontend:  # Next.js :3000
  nginx:     # 反向代理 :80
```

### 部署命令

```bash
git clone <repo>
cd industrial-park-agent
cp .env.example .env  # 填写 OPENAI_API_KEY
docker compose up -d
# 访问 http://localhost
```

---

## 十、里程碑

| 里程碑 | 日期 | 验收标准 |
|--------|------|---------|
| M0: 基础设施就绪 | Day 2 | make dev 一键启动 |
| M1: Supervisor 跑通 | Day 4 | 真实 LLM 意图识别 + Agent 调度 |
| M2: 核心 Agent 协作 | Day 7 | Investment + Risk + Policy 三 Agent 协同 |
| M3: 全链路闭环 | Day 9 | 6 Agent + 全部 API |
| M4: 前端交互 | Day 12 | Chat + Trace + Dashboard |
| M5: Demo 就绪 | Day 15 | 5 分钟完整演示 |

---

**计划完成。第三阶段：开始 Sprint 0 实现。**
