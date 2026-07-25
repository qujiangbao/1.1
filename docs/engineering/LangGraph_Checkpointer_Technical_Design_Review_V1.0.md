# LangGraph Checkpointer + Conversation Memory — Technical Design Review V1.0

> **P2 Implementation-Level Design**  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-25  
> **前置**: [LangGraph_Checkpointer_Design_V1.0.md](./LangGraph_Checkpointer_Design_V1.0.md) (Architecture Review ✅)

---

## 1. Audit 发现与关键决策

### 1.1 审计结论

| 文件 | 当前状态 | P2 需要 |
|------|---------|---------|
| `graph.py:125` | `MemorySaver()` 硬编码 | 条件初始化 `AsyncPostgresSaver` |
| `graph.py` | `build_supervisor_graph()` 同步 | 需支持 async setup（`await checkpointer.setup()`） |
| `supervisor_nodes.py` | 7 个同步节点 | 不变（同步 node 兼容 async checkpointer） |
| `state.py` | 无 `thread_id` 显式字段 | 已有 `conversation_id`，复用为 thread_id |
| `runtime.py:57-64` | Conversation 5 字段 | +3 字段：`thread_id`, `message_count`, `last_message_at` |
| `config.py:12` | `database_enabled: bool = False` | ✅ 已有，无需改动 |
| `api/v1/agent.py` | 仅 `POST /agent/chat` | +`GET /agent/checkpoint/{thread_id}` |
| `session.py` | `init_db()` create_all | ✅ 无需改动 |

### 1.2 关键架构决策

**决策 1: 同步节点 + 异步 Checkpointer**

LangGraph 架构中，`checkpointer` 在 graph 编译时注入。图的 `ainvoke()` 异步执行，但每个 `node` 函数可以是同步的。LangGraph 的 `AsyncPostgresSaver` 在后台自动处理 checkpoint 序列化/反序列化 —— 节点代码无需感知。

```
graph.ainvoke(state, config)      ← 异步
  ├─ user_input_node(state)        ← 同步，返回后自动 checkpoint
  ├─ intent_recognition_node(state) ← 同步，返回后自动 checkpoint
  └─ ...
```

**结论**: supervisor_nodes.py 的 7 个节点保持同步，不需要改为 async。

**决策 2: graph 编译时机**

`AsyncPostgresSaver` 需要 `await checkpointer.setup()` 建表。当前 `build_supervisor_graph()` 是同步函数。

方案：使用懒初始化 + async setup 模式。

```python
# graph.py 改造
_supervisor_graph = None
_checkpointer = None
_setup_done = False

async def get_supervisor_graph() -> StateGraph:
    global _supervisor_graph, _checkpointer, _setup_done
    if _supervisor_graph is None:
        settings = get_settings()
        if settings.database_enabled:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            _checkpointer = AsyncPostgresSaver.from_conn_string(settings.database_url)
            if not _setup_done:
                await _checkpointer.setup()
                _setup_done = True
        else:
            _checkpointer = MemorySaver()
        workflow = _build_workflow()
        _supervisor_graph = workflow.compile(checkpointer=_checkpointer)
    return _supervisor_graph
```

**决策 3: DatabaseTool 同步化**

supervisor_nodes.py 的 node 函数是同步的。如果需要 DB 写入（保存 conversation、agent_task 等），有两个选择：

- A) 把 node 改成 `async def` — 影响面大，风险高
- B) 使用同步 DatabaseTool，内部用 `asyncio.run()` 或同步 DB 连接 — 简单可靠

选择 **B**：DatabaseTool 提供同步方法，内部通过同步连接或 `asyncio.get_event_loop()` 调用异步 DB。

但更优方案：**不在 node 中直接写 DB**。让 LangGraph 的 checkpointer 自动管理 checkpoint，业务数据（agent_task, agent_execution, agent_trace）通过 API 层写入，而不是在 graph node 内部。

```
graph node (同步)          → LangGraph checkpointer 自动保存 checkpoint
API endpoint (async)       → 在 ainvoke 前后写 agent_task / conversation
```

**结论**: DatabaseTool 用于 API 层、恢复查询、health check，不在 node 内部调用。

**决策 4: 对话记忆注入**

历史消息注入发生在 `user_input_node`：

```python
def user_input_node(state: SupervisorState) -> SupervisorState:
    # P2 新增: 从 state["history_messages"] 注入历史上下文
    history = state.get("history_messages", [])
    if history:
        state["messages"] = history + state["messages"]
    # ... 原有逻辑不变
```

`history_messages` 由 API 层在调用 `graph.ainvoke()` 前设置，通过 `DatabaseTool.load_conversation_history()` 查询。

---

## 2. 文件级变更方案

### 2.1 graph.py — 核心改造

**变更类型**: 🟡 中等（~25 行变更）

```python
# 变更前 (line 86-136)
def build_supervisor_graph() -> StateGraph:
    from app.langgraph.nodes.supervisor_nodes import (...)
    workflow = StateGraph(SupervisorState)
    # ... 注册节点 ...
    return workflow.compile(checkpointer=MemorySaver())

_supervisor_graph = None
def get_supervisor_graph() -> StateGraph:
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = build_supervisor_graph()
    return _supervisor_graph

# 变更后
def _build_workflow() -> StateGraph:
    """构建 workflow（不含 checkpointer）"""
    from app.langgraph.nodes.supervisor_nodes import (...)
    workflow = StateGraph(SupervisorState)
    # ... 注册节点 (不变) ...
    return workflow

_supervisor_graph = None
_checkpointer = None
_setup_done = False

async def get_supervisor_graph() -> StateGraph:
    global _supervisor_graph, _checkpointer, _setup_done
    if _supervisor_graph is not None:
        return _supervisor_graph

    settings = get_settings()
    if settings.database_enabled:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            _checkpointer = AsyncPostgresSaver.from_conn_string(settings.database_url)
            if not _setup_done:
                await _checkpointer.setup()
                _setup_done = True
            logger.info("Checkpointer: AsyncPostgresSaver (PostgreSQL)")
        except Exception as e:
            logger.error("Failed to init Postgres checkpointer: %s, falling back to MemorySaver", e)
            _checkpointer = MemorySaver()
    else:
        _checkpointer = MemorySaver()
        logger.info("Checkpointer: MemorySaver (in-memory)")

    workflow = _build_workflow()
    _supervisor_graph = workflow.compile(checkpointer=_checkpointer)
    return _supervisor_graph
```

**重要**: `get_supervisor_graph()` 从同步变为异步。需要在所有调用点改为 `await get_supervisor_graph()`。

**影响范围**:
- `app/api/v1/agent.py:18` — 已有 `graph = get_supervisor_graph()`, 改为 `await`
- 任何其他调用点（测试、其他 API）

### 2.2 supervisor_nodes.py — 3 个节点微调

**变更类型**: 🟢 小（~25 行变更）

#### user_input_node（line 54-62）

```python
def user_input_node(state: SupervisorState) -> SupervisorState:
    state["status"] = "running"
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    state["trace_id"] = str(uuid4())
    state["agent_results"] = {}
    state["trace_steps"] = []
    state["error_count"] = 0
    state["retry_count"] = 0
    # P2 新增: 注入对话历史
    history = state.get("history_messages", [])
    if history:
        existing = state.get("messages", [])
        state["messages"] = history + existing
    return state
```

#### agent_router_node（line 150-185）

当前 `agent_router_node` 已有跳过 completed task 的逻辑（line 158-160），但状态机不完整。P2 增强：

```python
def agent_router_node(state: SupervisorState) -> SupervisorState:
    task_plan = state.get("task_plan", [])
    idx = state.get("current_task_index", 0)

    if idx >= len(task_plan):
        return state

    task = task_plan[idx]

    # P2 增强: 跳过 completed 和 failed 的 task
    if task.get("status") in ("completed", "failed"):
        state["current_task_index"] = idx + 1
        return state

    task["status"] = "running"
    agent = task["agent"]
    # ... 原有执行逻辑不变 ...
```

#### final_response_node（line 226-229）

```python
def final_response_node(state: SupervisorState) -> SupervisorState:
    state["status"] = "completed"
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    # P2 新增: 保存本轮对话消息到 history_messages 供下次恢复
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": state.get("final_response", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    state["messages"] = messages
    return state
```

### 2.3 state.py — thread_id 显式化

**变更类型**: 🟢 小（+2 行）

```python
class SupervisorState(TypedDict):
    # ... 现有字段不变 ...
    
    # P2 新增: 对话历史注入
    history_messages: Optional[List[Dict]]  # ← API 层注入的历史消息
    
    # 注: conversation_id 已存在，复用为 LangGraph thread_id
```

### 2.4 runtime.py — Conversation 3 字段扩展

**变更类型**: 🟢 小（+4 行）

```python
class Conversation(Base):
    __tablename__ = "conversation"

    conversation_id = Column(String(50), primary_key=True)
    user_id = Column(String(50))
    title = Column(String(500))
    status = Column(String(30), default="active")
    # P2 新增
    thread_id = Column(String(50), nullable=True)       # LangGraph thread_id (同 conversation_id)
    message_count = Column(Integer, default=0)
    last_message_at = Column(DateTime, nullable=True)
    created_time = Column(DateTime, default=datetime.utcnow)
    # P2 新增
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 2.5 app/tools/database_tool.py — 新建

**变更类型**: 🟢 新文件（~120 行）

```python
"""DatabaseTool — Agent 状态持久化工具

设计原则:
  - 同步方法（supervisor nodes 是同步的，但 node 内不调用 DB）
  - API 层在 graph 调用前后使用此工具
  - 仅 Supervisor 可访问（通过 ToolGateway 权限控制）
  - database_enabled=false 时所有方法静默跳过
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseTool:
    """数据库持久化工具 — 唯一数据访问通道"""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    # ── Conversation ──
    
    async def save_conversation(self, conv_id: str, user_id: str,
                                title: str = "", thread_id: str = "") -> None:
        """创建或更新对话记录"""
        if not self.enabled:
            return
        from app.database.session import SessionLocal
        from app.database.models.runtime import Conversation
        async with SessionLocal() as db:
            # upsert
            ...

    async def load_conversation_history(self, conv_id: str, limit: int = 10
                                        ) -> List[Dict[str, Any]]:
        """加载最近 N 轮对话消息"""
        if not self.enabled:
            return []
        # 从 agent_task.plan JSONB 或 messages 表读取
        ...

    # ── Agent Task ──
    
    async def save_agent_task(self, task: Dict[str, Any]) -> None:
        """Upsert agent_task"""
        if not self.enabled:
            return
        ...

    async def load_agent_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """加载任务记录"""
        ...

    # ── Agent Execution ──
    
    async def save_agent_execution(self, execution: Dict[str, Any]) -> None:
        """写入 agent_execution 记录"""
        ...

    # ── Checkpoint Status (读取 LangGraph 自动管理的 checkpoints 表) ──
    
    async def get_checkpoint_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """读取 LangGraph checkpoints 表的最新状态"""
        ...

    # ── Health ──
    
    async def health_check(self) -> bool:
        """数据库连通性检查"""
        ...


# 全局单例
_db_tool: Optional[DatabaseTool] = None


def get_database_tool() -> DatabaseTool:
    global _db_tool
    if _db_tool is None:
        from app.config import get_settings
        _db_tool = DatabaseTool(enabled=get_settings().database_enabled)
    return _db_tool
```

### 2.6 api/v1/agent.py — agent_chat 改造 + 新端点

**变更类型**: 🟡 中等（~40 行变更）

```python
# 变更前
@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid4())
    task_id = str(uuid4())
    started = time.perf_counter()
    
    graph = get_supervisor_graph()                          # 同步
    state = {
        "user_id": "demo-user",
        "conversation_id": conversation_id,
        "user_query": request.message,
        "user_role": "park_manager",
        "messages": [],
        "status": "idle",
        "trace_id": str(uuid4()),
    }
    config = {"configurable": {"thread_id": task_id}}       # thread_id = task_id
    result = await graph.ainvoke(state, config)
    ...

# 变更后
@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid4())
    task_id = str(uuid4())
    started = time.perf_counter()
    
    # P2: 注入对话历史
    db_tool = get_database_tool()
    history = await db_tool.load_conversation_history(conversation_id)
    
    # P2: 保存/更新 conversation 元数据
    await db_tool.save_conversation(
        conv_id=conversation_id,
        user_id=request.user_id or "demo-user",
        title=request.message[:50],
        thread_id=conversation_id,  # thread_id = conversation_id
    )
    
    graph = await get_supervisor_graph()                    # P2: 异步
    state = {
        "user_id": request.user_id or "demo-user",
        "conversation_id": conversation_id,
        "user_query": request.message,
        "user_role": "park_manager",
        "messages": [],
        "history_messages": history,                        # P2: 注入历史
        "status": "idle",
        "trace_id": str(uuid4()),
    }
    config = {"configurable": {"thread_id": conversation_id}}  # P2: thread_id = conversation_id
    result = await graph.ainvoke(state, config)
    
    response = result.get("final_response", "")
    agents = list(result.get("agent_results", {}).keys())
    
    # P2: 保存 agent_task 记录
    await db_tool.save_agent_task({
        "task_id": task_id,
        "conversation_id": conversation_id,
        "user_id": request.user_id or "demo-user",
        "intent": result.get("intent", ""),
        "goal": request.message,
        "priority": "medium",
        "plan": {"task_plan": result.get("task_plan", [])},
        "status": result.get("status", "completed"),
        "result": {"response": response, "agents_used": agents},
    })
    
    return ChatResponse(
        task_id=task_id,
        conversation_id=conversation_id,
        status=result.get("status", "completed"),
        response=response,
        agents_used=agents,
        trace_id=result.get("trace_id", ""),
        execution_time_ms=max(1, int((time.perf_counter() - started) * 1000)),
    )


# P2 新增: Checkpoint 状态查询端点
@router.get("/agent/checkpoint/{thread_id}")
async def get_checkpoint_status(thread_id: str):
    """查询 Agent 执行进度（从 LangGraph checkpoints 表读取）"""
    db_tool = get_database_tool()
    status = await db_tool.get_checkpoint_status(thread_id)
    if status is None:
        return {"thread_id": thread_id, "status": "not_found"}
    return status
```

### 2.7 config.py — 无需改动

已有 `database_enabled: bool = False` 和 `database_url`。P2 不需要新增配置项。

### 2.8 session.py — 无需改动

`init_db()` 的 `Base.metadata.create_all()` 会自动创建新增字段。

---

## 3. 数据流全链路

### 3.1 请求全流程（database_enabled=true）

```
POST /agent/chat { conversation_id: "C001", message: "分析广州数控风险" }
│
├─ 1. DatabaseTool.load_conversation_history("C001")
│     → 返回最近 10 条消息（含 user + assistant）
│
├─ 2. DatabaseTool.save_conversation("C001", ...)
│     → upsert conversation 表
│
├─ 3. await get_supervisor_graph()
│     → AsyncPostgresSaver.from_conn_string(db_url)
│     → await checkpointer.setup()  (首次创建 checkpoint 表)
│     → workflow.compile(checkpointer=checkpointer)
│
├─ 4. graph.ainvoke(state, {"configurable": {"thread_id": "C001"}})
│     │
│     ├─ user_input_node(state)
│     │    → 注入 history_messages → messages
│     │    → [自动 checkpoint #1 → checkpoints 表]
│     │
│     ├─ intent_recognition_node(state)
│     │    → [自动 checkpoint #2]
│     │
│     ├─ task_planner_node(state)
│     │    → [自动 checkpoint #3]
│     │
│     ├─ agent_router_node(state)
│     │    → 执行 RiskAgent
│     │    → [自动 checkpoint #4]
│     │
│     ├─ result_validator_node(state)
│     │    → [自动 checkpoint #5]
│     │
│     ├─ result_aggregator_node(state)
│     │    → LLM 生成报告
│     │    → [自动 checkpoint #6]
│     │
│     └─ final_response_node(state)
│          → [自动 checkpoint #7 — final]
│
├─ 5. DatabaseTool.save_agent_task(task)
│     → upsert agent_task 表
│
└─ 6. 返回 ChatResponse
```

### 3.2 恢复流程

```
用户刷新页面 → 重新请求相同 conversation_id

POST /agent/chat { conversation_id: "C001", message: "继续分析" }
│
├─ 1. 加载历史消息: 最近 10 条
│
├─ 2. graph.ainvoke(state, {"configurable": {"thread_id": "C001"}})
│     → LangGraph 从 checkpoints 表读取最新 checkpoint
│     → state 恢复到最新检查点
│     → 从当前 node 继续执行（或重新执行）
│
└─ 3. 返回结果
```

### 3.3 降级流程（database_enabled=false）

```
POST /agent/chat { message: "..." }
│
├─ DatabaseTool: 所有方法静默跳过 (self.enabled=False)
├─ get_supervisor_graph(): MemorySaver
├─ graph.ainvoke(state, ...) → 内存 checkpoint
└─ 与 v1.1 行为 100% 一致 ✅
```

---

## 4. 边界条件与容错

| 场景 | 处理 |
|------|------|
| PG 连接失败 + `database_enabled=true` | catch → ERROR log → 降级 MemorySaver |
| `checkpointer.setup()` 失败 | catch → ERROR log → 降级 MemorySaver |
| `conversation_id` 不存在 | 新建 conversation（无历史） |
| `thread_id` 无 checkpoint | 正常执行（首次执行） |
| `database_enabled=false` | DatabaseTool 静默跳过，MemorySaver |
| 并发请求同一 conversation_id | PostgreSQL 行锁 + LangGraph 序列化 |

---

## 5. 测试策略

### 5.1 Unit Tests (Mock 模式, DATABASE_ENABLED=false)

| # | 测试项 | 验证点 |
|---|--------|--------|
| 1 | `get_supervisor_graph()` 返回 MemorySaver graph | 与 v1.1 完全一致 |
| 2 | `user_input_node` 正确处理 `history_messages` | history 注入到 messages |
| 3 | `agent_router_node` 跳过 completed task | 状态机正确 |
| 4 | `final_response_node` 追加 assistant 消息 | messages 增长 |
| 5 | `DatabaseTool(enabled=False)` 所有方法静默 | 无报错 |
| 6 | `GET /agent/checkpoint/{id}` 返回 not_found | DB 未启用 |
| 7 | `POST /agent/chat` normal path | task_id, status, response |
| 8 | `POST /agent/chat` 带 conversation_id | 复用 conversation_id |

### 5.2 Integration Tests (需要 PostgreSQL)

| # | 测试项 |
|---|--------|
| 1 | AsyncPostgresSaver checkpoint 写入 checkpoints 表 |
| 2 | 进程重启后 thread_id 恢复 |
| 3 | agent_task 表写入 |
| 4 | conversation 表写入 + 历史查询 |
| 5 | PG 断开 → 降级 MemorySaver |

### 5.3 Backward Compatibility

- 所有现有 API 返回格式不变
- `DATABASE_ENABLED=false` 行为与 v1.1 100% 一致
- 所有 P0/P1 测试继续保持通过

---

## 6. 文件变更清单

| 文件 | 操作 | 预估行数 | 风险 |
|------|------|---------|------|
| `app/tools/database_tool.py` | **新建** | ~120 | 🟢 |
| `app/langgraph/graph.py` | 修改 | +20/-8 | 🟡 |
| `app/langgraph/nodes/supervisor_nodes.py` | 修改 | +15 | 🟢 |
| `app/langgraph/state.py` | 修改 | +2 | 🟢 |
| `app/database/models/runtime.py` | 修改 | +4 | 🟢 |
| `app/api/v1/agent.py` | 修改 | +35/-8 | 🟡 |
| `app/schemas/agent.py` | 修改 | +10 | 🟢 |
| **合计** | **7 文件** | **~170** | |

### 连锁改动

`get_supervisor_graph()` 从同步变为异步，需要检查所有调用点：

```bash
rg "get_supervisor_graph" --type py
```

预期影响范围：
- `app/api/v1/agent.py` — 已知，需要 `await`
- 任何测试文件 — 需要 `await`
- 任何其他 API 路由

---

## 7. Rollback 方案

如果 P2 引入问题，回滚步骤：

1. **代码层面**: `graph.py` 的 `get_supervisor_graph()` 在 `database_enabled=false` 时返回 MemorySaver，行为与 v1.1 100% 一致
2. **数据层面**: 新增字段 `nullable=True`，不影响现有数据
3. **部署层面**: 设置 `DATABASE_ENABLED=false` 即可完全回退到 v1.1 行为
4. **依赖**: `langgraph-checkpoint-postgres` 仅当 `database_enabled=true` 时才需要

---

*Generated by Hermes Agent · 2026-07-25 · Technical Design Review V1.0*
