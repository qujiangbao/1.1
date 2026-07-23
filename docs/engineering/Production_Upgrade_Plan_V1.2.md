# 广州产业AI运营官 — Production Upgrade Plan V1.2

> **状态**: DRAFT — 待审核  
> **基准版本**: v1.1 (Competition Gold, Git tag `Industrial_Park_Agent_Competition_Gold_v1.0`)  
> **分支策略**: `feature/production-upgrade-v1.2`，不触碰 main  
> **目标**: Demo Mock 数据 → 真实数据驱动生产系统  
> **日期**: 2026-07-23

---

## 0. 现状审计摘要

### 0.1 数据流现状

```
User → Supervisor (graph.py) → INTENT_ROUTING → Business Agent (executor.py)
                                                        ↓
                                                  Agent Nodes (risk_nodes.py, etc.)
                                                        ↓
                                                  ToolGateway (gateway.py)
                                                        ↓
                                                  _mock_*() 硬编码假数据 ← ⚠️ 全部替换点
```

### 0.2 关键发现

| 模块 | 当前状态 | 问题 |
|------|---------|------|
| ToolGateway | `_mock_enterprise_search()`, `_mock_scoring()` 等 15 个 mock 方法 | 零真实数据 |
| 数据库 | SQLAlchemy 模型已定义（Enterprise/Risk/Policy 等），`database_enabled=false` | 模型完备但未启用 |
| Checkpointer | `MemorySaver()` — 进程重启即丢失 | 无持久化 |
| Policy RAG | `policy_vector_search()` 返回硬编码政策 JSON | 无真实检索 |
| Alembic | 目录存在但为空 | 无迁移脚本 |
| 认证 | `auth_enabled=false`, `JWT_SECRET=change-this` | 无安全 |
| Agent 流 | 同步 `graph.invoke()` 阻塞返回 | 无实时推送 |

### 0.3 不可破坏的约束

- v1.1 main 分支保持比赛版本不变
- 所有 P0-P5 开发在 `feature/production-upgrade-v1.2` 分支
- Docker Compose 一键部署能力保持
- `DATABASE_ENABLED=false` 时 Demo 模式仍然可用

---

## 1. P0: Enterprise Data Tool（真实企业数据接入）

**目标**: RiskAgent 通过 ToolGateway 调用真实外部数据源，替换 mock 数据。

### 1.1 架构

```
RiskAgent (risk_nodes.py)
    ↓ data_request_node()
ToolGateway (gateway.py)
    ↓ invoke("RiskAgent", "enterprise_profile_get", ...)
EnterpriseDataTool (新文件: app/tools/enterprise_data.py)
    ├── 企业画像    → 天眼查 API / 企查查 API / 国家企业信用信息公示系统
    ├── 工商信息    → 统一社会信用代码、法人、注册资本、经营范围
    ├── 经营状态    → 存续/注销/异常、行政处罚、被执行人
    └── 风险事件    → 裁判文书、开庭公告、股权冻结
```

### 1.2 实现步骤

```
Phase 1a: EnterpriseDataTool 基础类
  └── app/tools/enterprise_data.py
      ├── class EnterpriseDataTool
      │   ├── get_profile(enterprise_id)      → 企业画像
      │   ├── get_business_info(credit_code)   → 工商信息
      │   ├── get_operation_status(enterprise_id) → 经营状态
      │   └── get_risk_events(enterprise_id)   → 风险事件
      └── class EnterpriseDataSource (抽象基类)
          ├── TianyanchaDataSource   (天眼查)
          ├── QichachaDataSource     (企查查)
          └── MockDataSource          (Demo 降级)

Phase 1b: ToolGateway 集成
  └── gateway.py
      ├── 替换 _mock_enterprise_search()   → EnterpriseDataTool
      ├── 替换 _mock_enterprise_profile()  → EnterpriseDataTool
      ├── 替换 _mock_enterprise_query()    → EnterpriseDataTool
      ├── 替换 _mock_scoring()             → 真实评分算法
      ├── 新增 enterprise_risk_events      → EnterpriseDataTool
      └── 保留 mock 作为 fallback（DATABASE_ENABLED=false 时）

Phase 1c: RiskAgent Nodes 增强
  └── risk_nodes.py
      ├── data_request_node()     → 调用真实 API
      ├── feature_extractor_node() → 基于真实数据计算风险特征
      └── predict_node()          → 基于历史风险事件预测
```

### 1.3 新增/修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/tools/enterprise_data.py` | **新建** | EnterpriseDataTool 核心类 |
| `backend/app/tools/__init__.py` | **新建** | Tools 包导出 |
| `backend/app/tools/gateway.py` | **修改** | 替换 mock → EnterpriseDataTool |
| `backend/app/langgraph/nodes/risk_nodes.py` | **修改** | 对接真实数据流 |
| `backend/app/config.py` | **修改** | 新增 `ENTERPRISE_DATA_SOURCE`, `TIANYANCHA_API_KEY` 等 |
| `.env.example` | **修改** | 新增数据源配置项 |

### 1.4 验收标准

- [ ] `EnterpriseDataTool.get_profile("ENT-001")` 返回真实企业数据（非 mock）
- [ ] RiskAgent 完整 Pipeline 跑通（validate → fetch → features → score → explain → predict → report）
- [ ] `DATABASE_ENABLED=false` 时降级到 MockDataSource，不报错
- [ ] 数据库 `enterprise` 表有真实数据写入

---

## 2. P1: Policy RAG + pgvector

**目标**: 真实 PDF 政策文档解析 → 分块 → Embedding → pgvector → 语义检索。

### 2.1 架构

```
PDF 政策文档
    ↓
DocumentParser (app/services/document_parser.py)
    ├── PDF  → PyMuPDF / pdfplumber
    ├── DOCX → python-docx
    └── HTML → BeautifulSoup
    ↓
TextChunker (app/services/chunker.py)
    ├── 固定大小分块 (512 tokens, overlap 50)
    ├── 章节感知分块
    └── 元数据保留 (标题/部门/日期/级别)
    ↓
EmbeddingService (app/services/embedding.py)
    ├── OpenAI text-embedding-3-small
    ├── DeepSeek embedding (如可用)
    └── 本地模型 fallback (BGE-M3)
    ↓
pgvector (PostgreSQL + pgvector extension)
    ├── 表: policy_chunks (id, policy_id, chunk_index, content, embedding vector(1536), metadata JSONB)
    └── 索引: IVFFlat / HNSW
    ↓
PolicyRetriever (app/services/retriever.py)
    ├── vector_search(query, top_k=10)     → 语义检索
    ├── hybrid_search(query, filters)      → 混合检索 (向量 + 关键词)
    └── rerank(chunks, enterprise_profile) → 企业适配重排
    ↓
PolicyAgent Nodes (policy_nodes.py)
    └── vector_search_node() → PolicyRetriever
```

### 2.2 实现步骤

```
Phase 2a: 基础设施
  └── requirements.txt 新增依赖
      ├── PyMuPDF / pdfplumber
      ├── pgvector (已存在)
      └── tiktoken (分块计数)

Phase 2b: 文档解析 + Embedding Pipeline
  └── backend/app/services/
      ├── document_parser.py    → parse_pdf(), parse_docx(), parse_html()
      ├── chunker.py            → chunk_text(), chunk_by_sections()
      ├── embedding.py          → EmbeddingService (OpenAI/DeepSeek/local)
      └── retriever.py          → PolicyRetriever

Phase 2c: 数据库 Schema
  └── 新增表: policy_chunks
      ├── id: SERIAL PRIMARY KEY
      ├── policy_id: VARCHAR(50) REFERENCES policy(policy_id)
      ├── chunk_index: INTEGER
      ├── content: TEXT
      ├── embedding: vector(1536)
      ├── metadata: JSONB
      └── 索引: CREATE INDEX ON policy_chunks USING ivfflat (embedding vector_cosine_ops)

Phase 2d: PolicyAgent 重构
  └── policy_nodes.py
      ├── enterprise_loader_node()   → 保留
      ├── vector_search_node()       → PolicyRetriever.vector_search()
      ├── metadata_filter_node()     → PolicyRetriever.hybrid_search()
      ├── policy_matcher_node()      → PolicyRetriever.rerank()
      └── 移除 ToolGateway mock 依赖

Phase 2e: 政策文档导入 CLI
  └── backend/scripts/import_policies.py
      ├── 扫描 docs/policies/*.pdf
      ├── 解析 → 分块 → Embedding → 写入 pgvector
      └── --dry-run / --force 模式
```

### 2.3 新增依赖

```
# requirements.txt 新增
pymupdf==1.24.0          # PDF 解析
tiktoken==0.7.0           # Token 计数
sentence-transformers==3.0.0  # 本地 embedding fallback (可选)
```

### 2.4 验收标准

- [ ] PDF 政策文档成功解析为文本
- [ ] 分块正确保留元数据（标题/部门/日期/级别）
- [ ] pgvector 索引查询 < 100ms (10K chunks)
- [ ] PolicyAgent.query("机器人产业补贴") 返回 5+ 条相关真实政策
- [ ] 语义检索相关性 Top-3 准确率 > 80%

---

## 3. P2: LangGraph Checkpointer 持久化

**目标**: Agent 状态 + 对话记忆持久化到 PostgreSQL，进程重启不丢失。

### 3.1 现状 vs 目标

| 项目 | 当前 | 目标 |
|------|------|------|
| Checkpointer | `MemorySaver()` | `AsyncPostgresSaver` |
| 对话记忆 | 无（每次新会话） | `Conversation` 表关联 |
| Agent 状态 | 内存中，重启丢失 | 持久化到 `agent_checkpoints` |
| 断点续传 | 不支持 | 支持 `thread_id` 恢复 |

### 3.2 实现步骤

```
Phase 3a: PostgreSQL Checkpointer
  └── graph.py
      ├── 替换 MemorySaver → AsyncPostgresSaver
      ├── 配置 checkpointer 使用 DATABASE_URL
      └── build_supervisor_graph() 返回 compiled graph with checkpointer

Phase 3b: Conversation Memory
  └── app/core/conversation_memory.py (新建)
      ├── 读取最近 N 轮对话
      ├── 注入到 SupervisorState.messages
      └── 关联 conversation_id

Phase 3c: Checkpoint Schema (LangGraph 自动管理)
  └── 表: checkpoint_blobs, checkpoint_writes, checkpoints
      └── LangGraph 在第一次调用时自动建表
```

### 3.3 验收标准

- [ ] Agent 执行后 checkpoint 写入 PostgreSQL
- [ ] 重启容器后用相同 `thread_id` 恢复执行
- [ ] 对话历史在页面刷新后保持
- [ ] Supervisor graph 编译不报错

---

## 4. P3: WebSocket / SSE 实时 Agent 流

**目标**: 前端实时看到 Agent 执行过程，而不是等待全部完成后一次性返回。

### 4.1 架构

```
前端 (Next.js)
    ↓ WebSocket / SSE 连接
    ↓ ws://backend:8000/ws/agent/{task_id}
后端 (FastAPI WebSocket)
    ↓ agent_router_node() → 每步 yield 事件
事件流:
    { type: "agent_start",    agent: "RiskAgent", timestamp: "..." }
    { type: "tool_call",      tool: "enterprise_profile_get", params: {...} }
    { type: "tool_result",    result: {...}, duration_ms: 120 }
    { type: "node_complete",  node: "scoring", data: { score: 85 } }
    { type: "agent_complete", result: {...}, total_ms: 4500 }
    { type: "error",          message: "...", agent: "RiskAgent" }
```

### 4.2 实现步骤

```
Phase 4a: 后端 WebSocket 端点
  └── app/api/v1/ws.py (新建)
      ├── @router.websocket("/ws/agent/{task_id}")
      ├── 接收 task_id, 启动 Agent 执行
      └── 每步 yield JSON 事件

Phase 4b: Agent 执行流改造
  └── graph.py / supervisor_nodes.py
      ├── agent_router_node() 改为 async generator
      └── 每个 graph node 之间 emit 事件

Phase 4c: 前端 SSE 消费
  └── frontend/src/app/agent/workspace/page.tsx (修改)
      ├── EventSource → /api/v1/agent/stream/{task_id}
      └── 实时渲染 Agent 执行卡片

Phase 4d: Docker Nginx / CORS
  └── docker-compose.yml / next.config.js
      ├── WebSocket 代理配置
      └── CORS 允许 ws://
```

### 4.3 验收标准

- [ ] WebSocket 连接成功建立
- [ ] 前端实时显示 Agent 执行步骤（非一次性返回）
- [ ] DAG 图实时高亮当前节点
- [ ] 断线重连机制

---

## 5. P4: RBAC（基于角色的访问控制）

**目标**: 园区管理员、部门主管、普通员工三级权限。

### 5.1 实现步骤

```
Phase 5a: 数据模型
  └── 新增表: users, roles, permissions, user_roles, role_permissions
      ├── roles: admin, park_manager, dept_head, staff, viewer
      └── permissions: agent.execute, dashboard.view, enterprise.read, ...

Phase 5b: 中间件
  └── app/core/security.py (扩展)
      ├── require_role("admin")
      ├── require_permission("enterprise.read")
      └── 装饰器 @has_permission

Phase 5c: API 保护
  └── 所有 /api/v1/* 路由添加权限检查
      ├── Agent 调用 → require_permission("agent.execute")
      ├── 企业数据 → require_permission("enterprise.read")
      └── 管理功能 → require_role("admin")
```

### 5.3 验收标准

- [ ] 无权限用户访问 API 返回 403
- [ ] 角色切换后权限即时生效
- [ ] JWT token 包含角色信息

---

## 6. P5: Alembic Migration

**目标**: 数据库 Schema 版本化管理，支持升级/回滚。

### 6.1 实现步骤

```
Phase 6a: 初始化
  └── cd backend && alembic init -t async alembic
      └── 配置 alembic.ini → DATABASE_URL
      └── 配置 env.py → 导入所有 SQLAlchemy models

Phase 6b: 生成迁移
  └── alembic revision --autogenerate -m "initial_schema"
      ├── enterprise, enterprise_profile, industry
      ├── policy, policy_chunks (P1 新增)
      ├── risk
      ├── agent_task, agent_execution, agent_trace, conversation
      ├── users, roles, permissions (P4 新增)
      └── alembic upgrade head

Phase 6c: CI/CD 集成
  └── Dockerfile / docker-compose.yml
      ├── 启动前: alembic upgrade head
      └── 失败则阻止启动
```

### 6.3 验收标准

- [ ] `alembic upgrade head` 成功建表
- [ ] `alembic downgrade -1` 成功回滚
- [ ] `alembic revision --autogenerate` 检测到新模型变更

---

## 7. 实施路线图

```
Week 1: P0 Enterprise Data Tool
  ├── Day 1-3: EnterpriseDataTool + Tianyancha/Qichacha API 对接
  ├── Day 4-5: ToolGateway 替换 mock → EnterpriseDataTool
  └── Day 5:   RiskAgent 真实数据流验证

Week 2: P1 Policy RAG + P5 Alembic
  ├── Day 1-2: P5 Alembic 初始化 + 自动生成迁移
  ├── Day 2-4: DocumentParser + Chunker + EmbeddingService
  ├── Day 4-5: PolicyRetriever + pgvector 索引
  └── Day 5-6: PolicyAgent 重构 + 验收

Week 3: P2 Checkpointer + P3 WebSocket
  ├── Day 1-2: AsyncPostgresSaver 集成
  ├── Day 3-4: WebSocket/SSE 后端
  └── Day 5-6: 前端实时 Agent 流 + 验证

Week 4: P4 RBAC + 集成测试
  ├── Day 1-3: RBAC 实现
  ├── Day 4-5: 全链路集成测试
  └── Day 6:   生产部署演练
```

---

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 天眼查/企查查 API 限流 | 高 | P0 阻塞 | 实现本地缓存 (Redis) + 降级 MockDataSource |
| DeepSeek Embedding 不可用 | 中 | P1 延迟 | BGE-M3 本地 fallback |
| pgvector 索引构建慢 | 中 | P1 延迟 | 先导入后建索引，分批处理 |
| WebSocket 连接不稳定 | 中 | P3 降级 | SSE 作为 fallback，自动重连 |
| 外部 API 费用超预算 | 低 | P0 成本 | 请求合并 + 缓存策略 |

---

## 9. 文件变更汇总

| P# | 新建文件 | 修改文件 | 估算行数 |
|----|---------|---------|---------|
| P0 | `backend/app/tools/enterprise_data.py` | `gateway.py`, `risk_nodes.py`, `config.py`, `.env.example` | ~500 |
| P1 | `backend/app/services/{parser,chunker,embedding,retriever}.py` | `policy_nodes.py`, `requirements.txt`, `business.py` (新增 policy_chunks) | ~800 |
| P2 | `backend/app/core/conversation_memory.py` | `graph.py`, `state.py` | ~200 |
| P3 | `backend/app/api/v1/ws.py` | `supervisor_nodes.py`, `workspace/page.tsx` | ~400 |
| P4 | `backend/app/database/models/rbac.py` | `security.py`, `api/v1/__init__.py` | ~300 |
| P5 | `backend/alembic/` (完整目录) | `Dockerfile`, `docker-compose.yml` | ~200 |
| **合计** | **~8 新文件** | **~10 修改文件** | **~2,400** |

> 注: 以上为代码净增量估算，不含测试文件和文档。

---

## 10. 下一步行动

- [ ] 审核本计划，确认优先级和范围
- [ ] 签署外部数据 API（天眼查/企查查）
- [ ] 创建 `feature/production-upgrade-v1.2` 分支
- [ ] 按 P0 → P5 顺序执行开发

---

*Generated by Hermes Agent · 2026-07-23 · v1.0 draft*
