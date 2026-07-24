# LangGraph Checkpointer + Conversation Memory — Technical Design V1.0

> **P2 Technical Design Review**  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-23

---

## 目录

1. [当前 MemorySaver 问题分析](#1-当前-memorysaver-问题分析)
2. [PostgreSQL Checkpointer 架构](#2-postgresql-checkpointer-架构)
3. [Checkpoint 数据模型](#3-checkpoint-数据模型)
4. [Conversation Memory 设计](#4-conversation-memory-设计)
5. [Supervisor 恢复机制](#5-supervisor-恢复机制)
6. [Agent 任务断点续跑机制](#6-agent-任务断点续跑机制)
7. [与现有代码集成方案](#7-与现有代码集成方案)
8. [Mock 模式兼容方案](#8-mock-模式兼容方案)

---

## 1. 当前 MemorySaver 问题分析

### 1.1 现状

```python
# graph.py:125
return workflow.compile(checkpointer=MemorySaver())
```

`MemorySaver` 是 LangGraph 内置的内存检查点存储。

### 1.2 问题清单

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| 1 | 进程重启丢失所有 checkpoint | 用户刷新页面后，进行中的 Agent 任务无法恢复 | 🔴 高 |
| 2 | 无跨请求状态共享 | 同一 conversation 的多轮对话无法关联 | 🔴 高 |
| 3 | 无对话历史 | Supervisor 每次都是"新会话"，无法利用历史上下文 | 🟡 中 |
| 4 | 内存泄漏风险 | 长时间运行，MemorySaver 持续增长不清理 | 🟡 中 |
| 5 | 无断点续跑 | Agent 任务执行到一半失败，必须从头重来 | 🟡 中 |
| 6 | 无状态审计 | 无法追溯"Agent 为什么做了这个决定" | 🟢 低 |

### 1.3 现有 Runtime 表利用情况

```sql
-- 表已定义，但 graph.py 不写这些表
agent_task      ← 未写入
agent_execution ← 未写入  
agent_trace     ← 未写入
conversation    ← 未写入
```

**结论**: Runtime 模型已完备，但 `graph.py` / `supervisor_nodes.py` 完全不写数据库，任务执行结果只存在于内存中。

---

## 2. PostgreSQL Checkpointer 架构

### 2.1 整体架构

```
Supervisor Graph
    │
    ├── graph.compile(checkpointer=AsyncPostgresSaver)
    │       │
    │       ├── 每个 node 执行后自动 checkpoint
    │       ├── thread_id → checkpoint 关联
    │       └── 重启后 thread_id 恢复执行
    │
    ├── DatabaseTool (新增) ← 唯一数据库访问通道
    │       │
    │       ├── save_checkpoint()
    │       ├── load_checkpoint(thread_id)
    │       ├── save_conversation()
    │       ├── load_conversation_history()
    │       ├── save_agent_task()
    │       └── load_agent_task(task_id)
    │
    └── Supervisor → DatabaseTool（通过 ToolGateway 规范访问）
```

### 2.2 约束遵守

```
❌ Supervisor 不直接访问数据库
❌ Agent 不直接访问数据库
❌ 不改变 Supervisor 架构（7 节点不变）
❌ 不改变 Agent 接口（execute_business_agent 签名不变）
✅ 所有持久化通过 DatabaseTool
✅ DatabaseTool 通过 ToolGateway 暴露（可选）
```

### 2.3 Checkpoint 时机

```
graph node 序列:
user_input → intent_recognition → task_planner → agent_router → result_validator → result_aggregator → finalize_response
     ↓              ↓                  ↓              ↓               ↓                  ↓                ↓
   checkpoint    checkpoint        checkpoint     checkpoint      checkpoint         checkpoint       checkpoint
                                                                                                   (最终状态)
```

每个 node 执行后，LangGraph 自动调用 checkpointer.put()。

### 2.4 thread_id 生命周期

```
POST /agent/execute { "user_query": "分析广州数控风险", "conversation_id": "CONV-001" }
    → SupervisorState.thread_id = "CONV-001"
    → graph.ainvoke(state, {"configurable": {"thread_id": "CONV-001"}})
    → 每个 node 后: checkpoint → postgres (keyed by thread_id)
    → 响应: { "task_id": "T-001", "thread_id": "CONV-001", "status": "completed" }

GET /agent/status?thread_id=CONV-001
    → DatabaseTool.load_checkpoint("CONV-001")
    → 返回当前 graph 状态（即使进程重启过）
```

---

## 3. Checkpoint 数据模型

### 3.1 LangGraph 自动建表

LangGraph 的 `AsyncPostgresSaver` 自动管理以下表：

```sql
-- LangGraph 自动创建，无需手动定义
CREATE TABLE checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    task_path TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE TABLE checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint BYTEA NOT NULL,
    metadata BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
```

### 3.2 与现有 Runtime 表的映射

```
LangGraph checkpoints    →  我们的 agent_task / agent_execution
    thread_id            →  conversation_id
    checkpoint           →  agent_task.plan (序列化的 SupervisorState)
    
我们增量管理的表:
    agent_task           →  任务生命周期 (created → running → completed/failed)
    agent_execution      →  每个 Agent 的执行记录
    agent_trace          →  每步 trace
    conversation         →  对话元数据
```

### 3.3 DatabaseTool Schema 操作

```python
# app/tools/database_tool.py (新增)

class DatabaseTool:
    """数据库持久化工具 — Supervisor 唯一数据访问通道"""

    # ── Checkpoint ──
    async def save_checkpoint(self, thread_id: str, state: dict) -> None:
        """保存 checkpoint 到 agent_task 表"""
        ...

    async def load_checkpoint(self, thread_id: str) -> Optional[dict]:
        """加载最近 checkpoint"""
        ...

    # ── Conversation ──
    async def save_conversation(self, conv_id: str, user_id: str, title: str) -> None:
        """Upsert 对话记录"""
        ...

    async def load_conversation_history(
        self, conv_id: str, limit: int = 10
    ) -> List[dict]:
        """加载最近 N 轮对话消息"""
        ...

    # ── Agent Task ──
    async def save_agent_task(self, task: dict) -> None:
        """Upsert agent_task 记录"""
        ...

    async def load_agent_task(self, task_id: str) -> Optional[dict]:
        """加载任务记录"""
        ...

    # ── Agent Execution ──
    async def save_agent_execution(self, execution: dict) -> None:
        """写入 agent_execution 记录"""
        ...

    # ── Status ──
    async def health_check(self) -> bool:
        """数据库连通性检查"""
        ...
```

---

## 4. Conversation Memory 设计

### 4.1 数据结构

```python
# Conversation 表（已有，补充字段）
class Conversation(Base):
    conversation_id = Column(String(50), primary_key=True)
    user_id = Column(String(50))
    title = Column(String(500))
    status = Column(String(30), default="active")
    # P2 新增
    thread_id = Column(String(50), nullable=True)      # ← LangGraph thread_id
    message_count = Column(Integer, default=0)          # ← 消息计数
    last_message_at = Column(DateTime, nullable=True)   # ← 最后消息时间
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow)
```

### 4.2 对话记忆注入

```
请求: POST /agent/execute { "conversation_id": "CONV-001", "user_query": "再详细分析一下" }
    ↓
1. 查找 conversation_id=CONV-001
    → 存在 → 加载最近 5 轮对话
    → 不存在 → 新建 CONV-001
    ↓
2. 将历史对话注入 SupervisorState.messages
    state["messages"] = [
        {"role": "user", "content": "分析广州数控风险", "timestamp": "..."},
        {"role": "assistant", "content": "风险评分 45，等级 LOW...", "timestamp": "..."},
        {"role": "user", "content": "再详细分析一下", "timestamp": "now"},
    ]
    ↓
3. Supervisor 执行时，LLM 可参考历史上下文
    → intent_recognition_node 理解 "再详细分析一下" 指的是广州数控
    → task_planner_node 复用历史结果 + 深入分析
    ↓
4. 执行完成后，将本轮对话追加到 messages
    → DatabaseTool.save_conversation() 更新
```

### 4.3 Memory 窗口策略

```
默认: 最近 10 轮对话（20 条消息）
配置: CONVERSATION_MEMORY_WINDOW=10
策略:
  - 超出窗口: 保留最早 2 轮 + 最近 8 轮
  - LLM 提示: 只注入最近 5 轮
  - 存储: 全部保留在 agent_task.result JSONB 中
```

---

## 5. Supervisor 恢复机制

### 5.1 正常流程

```
graph.ainvoke(state, config={"configurable": {"thread_id": conv_id}})
    → node 1: user_input          → checkpoint #1
    → node 2: intent_recognition  → checkpoint #2
    → node 3: task_planner        → checkpoint #3
    → node 4: agent_router        → checkpoint #4
    → node 5: result_validator    → checkpoint #5
    → node 6: result_aggregator   → checkpoint #6
    → node 7: finalize_response   → checkpoint #7 (final)
```

### 5.2 中断恢复

```
场景: agent_router 执行到一半，进程崩溃

恢复:
    graph.ainvoke(None, config={"configurable": {"thread_id": conv_id}})
    → LangGraph 从 checkpoints 表读取最新 checkpoint (#3)
    → 从 task_planner 之后继续执行
    → 跳过已完成的 agent_router 子任务
    → 继续 result_validator → ... → finalize_response
```

### 5.3 状态查询 API

```python
@router.get("/agent/checkpoint/{thread_id}")
async def get_checkpoint_status(thread_id: str):
    """
    查询 Agent 执行进度
    
    Response:
    {
        "thread_id": "CONV-001",
        "status": "running",           // idle | running | completed | failed
        "current_node": "agent_router", // 当前所在 node
        "completed_nodes": 3,           // 已完成 node 数
        "total_nodes": 7,
        "progress_pct": 42,
        "task_plan": [
            {"task_id":"T-001","agent":"RiskAgent","status":"completed"},
            {"task_id":"T-002","agent":"PolicyAgent","status":"pending"}
        ],
        "last_checkpoint_at": "2026-07-23T10:30:00"
    }
    """
    ...
```

---

## 6. Agent 任务断点续跑机制

### 6.1 场景

```
用户: "分析广州数控的风险，并匹配适用的机器人产业政策"
    ↓
Supervisor 拆分:
    Task 1: RiskAgent → 风险分析     [completed ✅]
    Task 2: PolicyAgent → 政策匹配    [pending ⏳]
    ↓ 此时进程重启
    ↓ 用户重新请求
    ↓
Supervisor 恢复:
    → task_plan 中 Task 1 已完成 → 跳过
    → 继续执行 Task 2
    → 最终聚合结果
```

### 6.2 实现: agent_router_node 改造

```python
def agent_router_node(state: SupervisorState) -> SupervisorState:
    plan = state["task_plan"]

    # P2: 跳过已完成的 task
    pending = [t for t in plan if t.get("status") != "completed"]
    if not pending:
        state["status"] = "all_completed"
        return state

    # 取第一个 pending task
    task = pending[0]
    task["status"] = "running"

    # 执行 Agent
    result = execute_business_agent(task["agent"], task, state)

    # P2: 持久化执行结果
    db_tool = get_database_tool()
    db_tool.save_agent_execution_sync({
        "execution_id": str(uuid4()),
        "task_id": task["task_id"],
        "agent_name": task["agent"],
        "status": result["status"],
        "output": result,
    })

    task["status"] = "completed" if result["status"] == "success" else "failed"
    state["agent_results"][task["agent"]] = result

    # 继续下一个 pending task（或返回）
    return state
```

### 6.3 状态机

```
Agent Task 状态:
    pending → running → completed
                     → failed → retry (retry_count < MAX)
                              → failed_permanent
```

---

## 7. 与现有代码集成方案

### 7.1 改动映射

```
文件                              改动                          影响
──────────────────────────────────────────────────────────────────────
graph.py                          MemorySaver → AsyncPostgresSaver  🔴 核心
                                  + 条件初始化（DATABASE_ENABLED）
supervisor_nodes.py               user_input_node: 注入历史消息      🟡 中等
                                  agent_router_node: 跳过已完成 task 🟡 中等
                                  finalize_response_node: 保存对话    🟡 中等
state.py                          SupervisorState: +thread_id 显式   🟢 小
runtime.py (models)               Conversation: +3 字段              🟢 小
database/session.py               init_db 增加 checkpoint 表检查     🟢 小
api/v1/agent.py                   新增 GET /agent/checkpoint/{id}    🟢 小
config.py                         +2 配置项                          🟢 小
tools/database_tool.py (新建)     DatabaseTool 核心类               🟢 新
```

### 7.2 graph.py 改动（核心）

```python
def build_supervisor_graph() -> StateGraph:
    # ... 所有节点注册不变 ...
    
    settings = get_settings()
    if settings.database_enabled:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        checkpointer = AsyncPostgresSaver.from_conn_string(settings.database_url)
        # 首次需要 setup
        # await checkpointer.setup()
    else:
        checkpointer = MemorySaver()  # 保持 Demo 兼容
    
    return workflow.compile(checkpointer=checkpointer)
```

### 7.3 不改变的部分

```
✅ supervisor_nodes.py 的 7 个节点结构不变
✅ INTENT_ROUTING 不变
✅ execute_business_agent() 接口不变  
✅ Agent graph (risk/policy/industry/...) 不变
✅ ToolGateway.invoke() 不变
✅ API 路由结构不变（只新增 1 个查询端点）
✅ Docker Compose 不变
```

### 7.4 DatabaseTool 注册

```python
# gateway.py (可选，通过 ToolGateway 暴露)
"database_save_checkpoint"    → database_tool.save_checkpoint_sync,
"database_load_checkpoint"    → database_tool.load_checkpoint_sync,
"database_save_conversation"  → database_tool.save_conversation_sync,
# 权限: 仅 Supervisor
"Supervisor": ["*"],
```

---

## 8. Mock 模式兼容方案

### 8.1 模式判断

```python
# config.py
DATABASE_ENABLED=false    → MemorySaver（v1.1 行为，完全一致）
DATABASE_ENABLED=true     → AsyncPostgresSaver（生产持久化）
```

### 8.2 双模式行为

```
DATABASE_ENABLED=false (Demo):
    → MemorySaver
    → 无对话记忆（每次新会话）
    → 无断点续跑
    → 与 v1.1 行为 100% 一致 ✅

DATABASE_ENABLED=true (Production):
    → AsyncPostgresSaver
    → 对话记忆保留最近 10 轮
    → 支持断点续跑
    → 进程重启不丢失

PG 连接失败 + DATABASE_ENABLED=true:
    → 打印 ERROR，降级到 MemorySaver
    → 不阻断 Agent 流程
```

### 8.3 DatabaseTool 降级

```python
class DatabaseTool:
    async def save_checkpoint(self, thread_id, state):
        if not database_enabled:
            logger.debug("Database disabled, skipping checkpoint save")
            return  # 静默跳过
        ...
```

---

## 9. 文件变更估算

| 类别 | 文件 | 行数 |
|------|------|------|
| 新建 | `app/tools/database_tool.py` | ~120 |
| 修改 | `app/langgraph/graph.py` | +15 |
| 修改 | `app/langgraph/nodes/supervisor_nodes.py` | +25 |
| 修改 | `app/langgraph/state.py` | +3 |
| 修改 | `app/database/models/runtime.py` | +5 |
| 修改 | `app/database/session.py` | +5 |
| 修改 | `app/api/v1/agent.py` | +20 |
| 修改 | `app/config.py` | +2 |
| **合计** | **8 文件** | **~195** |

---

## 10. 验收清单

- [ ] `DATABASE_ENABLED=false` → MemorySaver, 行为与 v1.1 一致
- [ ] `DATABASE_ENABLED=true` → AsyncPostgresSaver 编译成功
- [ ] 执行 Agent 任务后 checkpoint 写入 checkpoints 表
- [ ] 进程重启后用相同 thread_id 恢复执行
- [ ] 对话历史在 conversation 表中持久化
- [ ] agent_task 表记录任务生命周期
- [ ] agent_execution 表记录每个 Agent 执行
- [ ] `/agent/checkpoint/{thread_id}` 返回正确进度
- [ ] PG 连接失败 → 降级 MemorySaver + ERROR log
- [ ] 现有 Agent tests 全部通过

---

*Generated by Hermes Agent · 2026-07-23 · LangGraph Checkpointer Design V1.0*
