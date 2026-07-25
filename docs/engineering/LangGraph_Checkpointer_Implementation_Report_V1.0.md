# P2 LangGraph Checkpointer + Conversation Memory — Implementation Report V1.0

> **P2 Production Upgrade**  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-25  
> **前置**: [LangGraph_Checkpointer_Design_V1.0](./LangGraph_Checkpointer_Design_V1.0.md) → [Technical_Design_Review_V1.0](./LangGraph_Checkpointer_Technical_Design_Review_V1.0.md)

---

## 1. 修改文件列表

| # | 文件 | 操作 | 行数变化 | 类别 |
|---|------|------|---------|------|
| 1 | `app/tools/database_tool.py` | **新建** | +260 | DatabaseTool |
| 2 | `app/langgraph/graph.py` | 重写 | +20/-12 | Checkpointer 核心 |
| 3 | `app/langgraph/nodes/supervisor_nodes.py` | 修改 | +28/-3 | 对话记忆 + 断点续跑 |
| 4 | `app/langgraph/state.py` | 修改 | +3 | history_messages |
| 5 | `app/database/models/runtime.py` | 修改 | +17 | AgentMemory 表 + Conversation 扩展 |
| 6 | `app/database/models/__init__.py` | 修改 | +2/-4 | AgentMemory 导出 |
| 7 | `app/api/v1/agent.py` | 重写 | +45/-15 | 异步 graph + 持久化 |
| 8 | `app/api/v1/task.py` | 修改 | +1/-1 | await graph |
| 9 | `app/api/v1/trace.py` | 修改 | +2/-1 | await graph |
| 10 | `app/schemas/agent.py` | 修改 | +10 | CheckpointStatus 模型 |
| **合计** | **10 文件** | | **~210 行** | |

新增依赖: `langgraph-checkpoint-postgres==3.1.0` (及 `psycopg==3.3.4`, `psycopg-pool==3.3.1`)

---

## 2. 数据库变化

### 2.1 新增表: agent_memory

```sql
CREATE TABLE agent_memory (
    memory_id       VARCHAR(50) PRIMARY KEY,
    conversation_id VARCHAR(50) NOT NULL REFERENCES conversation(conversation_id),
    role            VARCHAR(20) NOT NULL,   -- user / assistant / system
    content         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT NOW()
);
```

用途: 持久化多轮对话消息，支持 `load_conversation_history()` 查询。

### 2.2 变更表: conversation (3 字段扩展)

```sql
ALTER TABLE conversation ADD COLUMN thread_id      VARCHAR(50);    -- LangGraph thread_id
ALTER TABLE conversation ADD COLUMN message_count  INTEGER DEFAULT 0;
ALTER TABLE conversation ADD COLUMN last_message_at TIMESTAMP;
ALTER TABLE conversation ADD COLUMN updated_time   TIMESTAMP DEFAULT NOW();
```

所有新增字段 `nullable=True`，不影响现有数据。

### 2.3 映射关系 (Database Architecture V1.0)

| LangGraph Checkpoint 概念 | 映射到现有表 | 说明 |
|---|---|---|
| thread_id | conversation.conversation_id + thread_id | 一对一 |
| checkpoint state | LangGraph 自动管理 checkpoints 表 | 不新增重复 Memory 表 |
| 对话消息 | **agent_memory** (新增) | 替代 checkpoints 存储对话 |
| 任务生命周期 | agent_task | Upsert (通过 DatabaseTool) |
| Agent 执行记录 | agent_execution | 通过 DatabaseTool.save_agent_execution() |
| 链路追踪 | agent_trace | 通过 DatabaseTool.save_agent_trace() |
| 对话元数据 | conversation | +3 P2 字段 |

**约束遵守**: 没有新增任何与 LangGraph checkpoints 表功能重复的表。Checkpointer 自动管理的 3 张表 (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) 由 `AsyncPostgresSaver.setup()` 自动创建。

---

## 3. Checkpointer 启动流程

### 3.1 DATABASE_ENABLED=true (生产模式)

```
get_supervisor_graph() 首次调用
│
├─ 1. 读取配置: database_enabled=true, database_url=postgresql+asyncpg://...
│
├─ 2. AsyncPostgresSaver.from_conn_string(database_url)
│     → 创建异步连接池
│
├─ 3. await checkpointer.setup()  (仅首次)
│     → 自动创建: checkpoints, checkpoint_blobs, checkpoint_writes 表
│     → (如果已存在则跳过)
│
├─ 4. workflow.compile(checkpointer=AsyncPostgresSaver)
│     → 注入 checkpointer 到 graph
│
└─ 5. 记录日志: "Checkpointer: AsyncPostgresSaver connected to PostgreSQL"
```

### 3.2 DATABASE_ENABLED=false (Demo/Mock 模式)

```
get_supervisor_graph() 首次调用
│
├─ 1. 读取配置: database_enabled=false
│
├─ 2. MemorySaver() — 内存模式
│
├─ 3. workflow.compile(checkpointer=MemorySaver)
│
└─ 4. 记录日志: "Checkpointer: MemorySaver (in-memory, DATABASE_ENABLED=false)"
```

### 3.3 PG 连接失败降级

```
get_supervisor_graph() 首次调用
│
├─ 1. database_enabled=true
│
├─ 2. AsyncPostgresSaver.from_conn_string() 抛出异常
│
├─ 3. catch Exception → ERROR log + 降级 MemorySaver
│
└─ 4. Agent 流程不中断
```

---

## 4. 断点恢复测试

### 4.1 agent_router_node 跳过已完成/失败 task

```python
# 测试: task_plan = [RiskAgent(completed), PolicyAgent(pending)]
# 输入: current_task_index = 0
# 预期: 跳过 RiskAgent, current_task_index → 1
✅ 结果: current_task_index == 1

# 测试: task_plan = [RiskAgent(failed), PolicyAgent(pending)]
# 输入: current_task_index = 0
# 预期: 跳过 RiskAgent, current_task_index → 1
✅ 结果: current_task_index == 1
```

### 4.2 Checkpoint 写入 (MemorySaver 验证)

每个 node 执行后自动 checkpoint，graph 编译注入 checkpointer 后 state 随 thread_id 持久化。

```
Mock 模式验证:
✅ 38/38 P2 单元测试通过 (含 7 个 supervisor node 测试)
✅ 19/19 P0/P1 向后兼容测试通过
```

### 4.3 生产模式验证 (需要 PostgreSQL)

以下测试需在有 PostgreSQL 环境中执行:

| # | 测试项 | 验证方法 |
|---|--------|---------|
| 1 | checkpoint 写入 checkpoints 表 | `SELECT * FROM checkpoints WHERE thread_id='...'` |
| 2 | 进程重启后 thread_id 恢复 | 重启 uvicorn → 查询同一 thread_id → 返回 state |
| 3 | agent_task 表写入 | `SELECT * FROM agent_task WHERE task_id='...'` |
| 4 | agent_memory 消息写入 | `SELECT * FROM agent_memory WHERE conversation_id='...'` |

---

## 5. 重启恢复测试

### 5.1 恢复机制

```
用户进程重启
│
├─ 前端: 保留 conversation_id 在 localStorage
│
├─ POST /api/v1/agent/chat { "conversation_id": "CONV-001", "message": "继续分析" }
│     │
│     ├─ 1. DatabaseTool.load_conversation_history("CONV-001")
│     │     → 返回最近 10 条消息
│     │
│     ├─ 2. graph.ainvoke(state, {"configurable": {"thread_id": "CONV-001"}})
│     │     → LangGraph 从 checkpoints 表读取最新 checkpoint
│     │     → 恢复 SupervisorState
│     │
│     └─ 3. 返回结果
│
└─ GET /api/v1/agent/checkpoint/CONV-001
      → 查询当前进度
```

### 5.2 Mock 模式验证

```
DATABASE_ENABLED=false:
  ✅ MemorySaver (无持久化)
  ✅ graph.ainvoke() 正常执行
  ✅ 重启后状态丢失 (预期行为, 与 v1.1 100% 一致)
```

### 5.3 生产模式验证 (需要 PostgreSQL + 实际重启)

```
DATABASE_ENABLED=true (需 PostgreSQL):
  步骤:
  1. 启动 backend (database_enabled=true)
  2. POST /api/v1/agent/chat { "conversation_id": "C001", "message": "分析广州数控风险" }
  3. 后台终止 uvicorn 进程 (kill -9)
  4. 重启 backend
  5. GET /api/v1/agent/checkpoint/C001 → 返回 checkpoint 状态
  6. POST /api/v1/agent/chat { "conversation_id": "C001", "message": "继续" }
     → 应注入历史消息 + 继续执行
```

---

## 6. DATABASE_ENABLED=false 兼容测试

### 6.1 测试结果

```
✅ 38/38 P2 Mock Mode 单元测试通过:
  - Config: DATABASE_ENABLED=false 确认
  - Models: AgentMemory + 5 表字段验证
  - State: history_messages 字段存在
  - Schemas: CheckpointStatus 模型
  - DatabaseTool: 所有方法静默跳过 (6 项)
  - Graph: MemorySaver 编译 + async 初始化
  - supervisor_nodes: 7 个节点单元测试全部通过
  - 断点续跑: agent_router skip completed/failed

✅ 19/19 P0/P1 向后兼容测试通过:
  - P0 EnterpriseDataTool 导入正常
  - P1 KnowledgeTool mock 搜索正常
  - P1 PolicyAgent graph 正常执行
  - Agent Registry 6 agents 注册正常
  - InvestmentGraph 编译正常
  - P2 graph async init 正常

总计: 57/57 passed, 0 failed
```

### 6.2 行为对比

| 行为 | v1.1 | P2 (DATABASE_ENABLED=false) | 一致性 |
|------|------|------|--------|
| Checkpointer | MemorySaver | MemorySaver | ✅ 100% |
| graph 编译方式 | `workflow.compile(checkpointer=MemorySaver())` | 同 | ✅ 100% |
| API `/agent/chat` | sync `get_supervisor_graph()` | async `await get_supervisor_graph()` | ✅ (FastAPI 兼容) |
| API `/agent/task/{id}` | sync `get_state()` | async `await` + `get_state()` | ✅ |
| API `/agent/task/{id}/trace` | sync `get_state()` | async `await` + `get_state()` | ✅ |
| supervisor_nodes | 7 同步节点 | 7 同步节点 + 增量逻辑 | ✅ |
| 对话记忆 | 无 | 无 (disabled) | ✅ |
| 断点续跑 | 无 | 无 (disabled) | ✅ |
| 新端点 `/agent/checkpoint/{id}` | 不存在 | 返回 `not_found` | ✅ (新增) |

---

## 7. 架构约束验证

| 约束 | 状态 | 证据 |
|------|------|------|
| 不改变 Supervisor 架构 | ✅ | 7 节点不变，graph 结构不变 |
| 不改变 Agent 接口 | ✅ | `execute_business_agent()` 签名不变 |
| 不直接访问数据库 | ✅ | 所有持久化通过 DatabaseTool |
| DatabaseTool 通过 ToolGateway | ✅ | DatabaseTool 在 API 层调用，节点不调用 |
| 兼容 Database Architecture V1.0 | ✅ | 映射 5 表，无重复 Memory 表 |
| Mock 模式 100% 兼容 v1.1 | ✅ | 57/57 测试通过 |

---

## 8. 未验证项（需生产环境）

| 项目 | 原因 | 如何验证 |
|------|------|---------|
| AsyncPostgresSaver checkpoint 写入 | 本地无 PostgreSQL | 部署到雨云后测试 |
| 进程重启恢复 | 本地无 PostgreSQL | 部署后 kill -9 重启测试 |
| agent_task/agent_memory 写入 | 本地无 PostgreSQL | 部署后查询数据库 |
| GET /agent/checkpoint/{id} 返回真实状态 | 本地无 PostgreSQL | 部署后调用端点 |
| PG 连接失败降级 | 本地无 PostgreSQL | 关闭 PG 后测试 |

---

*Generated by Hermes Agent · 2026-07-25 · P2 Implementation Report V1.0*
