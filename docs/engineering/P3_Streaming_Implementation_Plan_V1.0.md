# P3 Streaming — Implementation Plan V1.0

> **P3 SSE Streaming 实施计划**  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-25  
> **前置**: [WebSocket_Streaming_Architecture_V1.0](./WebSocket_Streaming_Architecture_V1.0.md) ✅ Approved

---

## 1. 实施概览

| 维度 | 值 |
|------|-----|
| 新建文件 | 6 |
| 修改文件 | 6 |
| 预估总行数 | ~550 |
| 前端改动 | ~250 行 (删除虚假动画 + 接入 SSE) |
| 后端改动 | ~300 行 |
| Mock 兼容 | STREAMING_ENABLED=false → 100% v1.2 行为 |

---

## 2. 新建文件详细设计

### 2.1 `backend/app/services/event_bus.py` (~100 行)

**位置**: `app/services/` (runtime 层，不放 langgraph 目录)

**职责**: 内存发布/订阅，每个 task_id 独立 channel

```python
class EventBus:
    """
    约束:
      - 不引入外部依赖 (Redis/消息队列)
      - 基于 asyncio.Queue，每个 task_id 独立 List[Queue]
      - publish() 使用 put_nowait() + try/except QueueFull，不阻塞调用方
      - 自动清理: unsubscribe 时检查空 channel 并删除
    """
    def __init__(self):
        self._subscriptions: dict[str, list[asyncio.Queue]] = {}

    async def subscribe(self, task_id: str, queue: asyncio.Queue) -> None: ...
    async def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None: ...
    async def publish(self, task_id: str, event_type: str, data: dict) -> None: ...

# 全局单例
def get_event_bus() -> EventBus: ...
```

**Queue 容量**: `asyncio.Queue(maxsize=256)` — 防止内存泄漏，满时丢弃最早事件

---

### 2.2 `backend/app/services/event_normalizer.py` (~80 行)

**职责**: 将 LangGraph 原始事件 + Supervisor 自定义事件 → 标准化 SSE 事件格式

**为什么必须经过 Normalizer**: 
- LangGraph 的 `astream_events` 输出格式与 Supervisor 的 `_emit_*` 格式不统一
- 前端只需消费一种标准格式，不需要区分事件来源
- 未来引入新事件类型时，只需加 Normalizer 映射，不改前端

```python
from enum import Enum

class StreamEventType(str, Enum):
    """标准化事件类型 — 前端唯一消费的 event name"""
    NODE_START    = "node_start"      # Supervisor 节点开始
    NODE_COMPLETE = "node_complete"   # Supervisor 节点完成
    AGENT_START   = "agent_start"     # Agent 开始执行
    AGENT_DONE    = "agent_done"      # Agent 执行完成
    AGENT_ERROR   = "agent_error"     # Agent 执行失败
    LLM_TOKEN     = "llm_token"       # LLM 流式 token
    DONE          = "done"            # 任务全部完成
    ERROR         = "error"           # 致命错误
    SNAPSHOT      = "snapshot"        # 重连快照
    HEARTBEAT     = "heartbeat"       # 心跳保活


class EventNormalizer:
    """标准化事件转换器
    
    输入: 原始事件 dict (来自 EventBus.publish 或 LangGraph astream_events)
    输出: {"type": StreamEventType, "data": {...}}
    
    规则:
      - supervisor_node → NODE_COMPLETE (data.node = 完成节点名)
      - agent_start → AGENT_START
      - agent_complete → AGENT_DONE
      - agent_error → AGENT_ERROR
      - llm_token → LLM_TOKEN
      - done → DONE
      - heartbeat → HEARTBEAT
      - snapshot → SNAPSHOT
    """
    
    @staticmethod
    def normalize(raw: dict) -> dict:
        """返回 {"type": "node_complete", "data": {...}}"""
        type_map = {
            "supervisor_node": StreamEventType.NODE_COMPLETE,
            "agent_start":     StreamEventType.AGENT_START,
            "agent_complete":  StreamEventType.AGENT_DONE,
            "agent_error":     StreamEventType.AGENT_ERROR,
            "llm_token":       StreamEventType.LLM_TOKEN,
            "done":            StreamEventType.DONE,
            "error":           StreamEventType.ERROR,
            "heartbeat":       StreamEventType.HEARTBEAT,
            "snapshot":        StreamEventType.SNAPSHOT,
        }
        event_type = type_map.get(raw.get("type"), StreamEventType.HEARTBEAT)
        return {"type": event_type.value, "data": raw.get("data", {})}
```

---

### 2.3 `backend/app/services/stream_executor.py` (~60 行)

**职责**: 后台执行 graph.ainvoke() + 通过 EventBus 发布事件，不阻塞 HTTP 响应

```python
async def execute_graph_with_events(
    graph, state: dict, config: dict,
    task_id: str, conversation_id: str,
    db_tool, user_message: str,
) -> None:
    """后台执行 Supervisor graph 并通过 EventBus 发布事件
    
    执行流程:
      1. graph.ainvoke(state, config) → 获取结果
      2. 发布 done 事件 (含 final_response, agents_used)
      3. 通过 db_tool 持久化 (agent_task, agent_memory)
    
    错误处理:
      - graph 执行失败 → 发布 error 事件
      - db 写入失败 → logger.error，不阻塞 done 事件
    """
    event_bus = get_event_bus()
    
    try:
        result = await graph.ainvoke(state, config)
        
        # 发布完成事件
        response = result.get("final_response", "")
        agents = list(result.get("agent_results", {}).keys())
        await event_bus.publish(task_id, "done", {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "status": result.get("status", "completed"),
            "final_response": response,
            "agents_used": agents,
            "trace_id": result.get("trace_id", ""),
        })
        
        # 持久化
        await db_tool.save_agent_task({...})
        await db_tool.save_message(conversation_id, "user", user_message)
        if response:
            await db_tool.save_message(conversation_id, "assistant", response[:2000])
            
    except Exception as e:
        await event_bus.publish(task_id, "error", {
            "task_id": task_id,
            "message": str(e),
        })
```

---

### 2.4 `backend/app/api/v1/stream.py` (~100 行)

**职责**: SSE 端点 + snapshot 端点

```python
router = APIRouter()


@router.get("/agent/stream/{task_id}")
async def agent_stream(task_id: str):
    """SSE 端点 — 订阅 Agent 执行实时事件流
    
    - 首次连接: 检查是否有已完成状态 → 发送 snapshot
    - 运行时: 转发 EventBus 事件 (经 EventNormalizer 标准化)
    - 30 秒无事件 → 发送 heartbeat
    - 收到 done 或 error → 关闭连接
    
    兼容性:
      - STREAMING_ENABLED=false → 返回 404 (Service Unavailable)
    """
    from app.config import get_settings
    if not get_settings().streaming_enabled:
        raise HTTPException(status_code=404, detail="Streaming is disabled")
    
    from app.services.event_bus import get_event_bus
    from app.services.event_normalizer import EventNormalizer
    
    event_bus = get_event_bus()
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    await event_bus.subscribe(task_id, queue)
    
    async def generate():
        try:
            # Step 1: 尝试发送 snapshot（重连场景）
            snapshot = await _build_snapshot(task_id)
            if snapshot:
                yield _sse_frame("snapshot", snapshot)
            
            # Step 2: 转发实时事件
            while True:
                try:
                    raw = await asyncio.wait_for(queue.get(), timeout=30)
                    normalized = EventNormalizer.normalize(raw)
                    yield _sse_frame(normalized["type"], normalized["data"])
                    if raw["type"] in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    yield _sse_frame("heartbeat", {})
        finally:
            await event_bus.unsubscribe(task_id, queue)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/agent/stream/{task_id}/snapshot")
async def agent_stream_snapshot(task_id: str):
    """获取当前任务状态快照 (用于初始加载或轮询降级)
    
    - 查询 LangGraph state
    - 返回当前进度: intent, task_plan, agent_results, status
    """
    from app.langgraph.graph import get_supervisor_graph
    graph = await get_supervisor_graph()
    state = graph.get_state({"configurable": {"thread_id": task_id}})
    if state is None or not state.values:
        return {"task_id": task_id, "status": "not_found"}
    sv = state.values
    return {
        "task_id": task_id,
        "status": sv.get("status", "unknown"),
        "intent": sv.get("intent"),
        "intents": sv.get("intents", []),
        "task_plan": [
            {"task_id": t.get("task_id"), "agent": t.get("agent"),
             "status": t.get("status"), "intent": t.get("intent")}
            for t in sv.get("task_plan", [])
        ],
        "agent_results": {
            agent: {"status": r.get("status"), "summary": (r.get("result") or {}).get("summary", "")}
            for agent, r in sv.get("agent_results", {}).items()
        },
        "started_at": sv.get("started_at"),
        "completed_at": sv.get("completed_at"),
    }


def _sse_frame(event_type: str, data: dict) -> str:
    """构建 SSE frame"""
    import json
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _build_snapshot(task_id: str) -> dict | None:
    """从 LangGraph state 构建快照"""
    try:
        from app.langgraph.graph import get_supervisor_graph
        graph = await get_supervisor_graph()
        state = graph.get_state({"configurable": {"thread_id": task_id}})
        if state and state.values:
            sv = state.values
            return {
                "task_id": task_id,
                "status": sv.get("status"),
                "intent": sv.get("intent"),
                "intents": sv.get("intents", []),
                "task_plan": [
                    {"task_id": t.get("task_id"), "agent": t.get("agent"),
                     "status": t.get("status")}
                    for t in sv.get("task_plan", [])
                ],
                "agent_results_summary": {
                    a: {"status": r.get("status"),
                        "summary": (r.get("result") or {}).get("summary", "")[:100]}
                    for a, r in sv.get("agent_results", {}).items()
                },
            }
    except Exception:
        pass
    return None
```

---

## 3. 修改文件详细设计

### 3.1 `backend/app/config.py` (+3 行)

```python
# 在 Policy RAG (P1) 段落后新增:
# Streaming (P3)
streaming_enabled: bool = True  # ← 默认开启; false 时降级 REST
```

### 3.2 `backend/app/api/v1/agent.py` (+20/-50 行)

**改造策略**: `POST /agent/chat` 双模式:
- `streaming_enabled=true` → 异步执行, 立即返回 `{ task_id, stream_url }`
- `streaming_enabled=false` → 同步执行, 与当前 v1.2 行为完全一致

```python
@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid4())
    task_id = str(uuid4())
    started = time.perf_counter()
    
    # [保持不变] DB tool, history load, conversation save
    from app.tools.database_tool import get_database_tool
    db_tool = get_database_tool()
    history = await db_tool.load_conversation_history(conversation_id)
    await db_tool.save_conversation(...)
    
    graph = await get_supervisor_graph()
    state = {...}
    config = {"configurable": {"thread_id": conversation_id}}
    
    settings = get_settings()
    
    # === P3 分支: 异步流式 ===
    if settings.streaming_enabled:
        asyncio.create_task(execute_graph_with_events(
            graph, state, config, task_id, conversation_id, db_tool, request.message,
        ))
        return ChatResponse(
            task_id=task_id, conversation_id=conversation_id,
            status="processing", response=None,
            stream_url=f"/api/v1/agent/stream/{task_id}",
        )
    
    # === v1.2 兼容: 同步执行 ===
    result = await graph.ainvoke(state, config)
    # ... 原有持久化 + 返回逻辑不变 ...
```

### 3.3 `backend/app/langgraph/nodes/supervisor_nodes.py` (+35 行)

**策略**: 在每个节点函数返回前添加事件发布调用。不改变节点逻辑。

**事件发布辅助函数** (新增在 module 顶部):

```python
# P3: EventBus 事件发布辅助
def _emit_node(state: SupervisorState, node_name: str):
    """发布 Supervisor 节点完成事件"""
    from app.services.event_bus import get_event_bus
    task_id = state.get("trace_id", "")
    if not task_id:
        return
    event_bus = get_event_bus()
    asyncio.ensure_future(event_bus.publish(task_id, "supervisor_node", {
        "node": node_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))


def _emit_agent_event(state: SupervisorState, event_type: str, data: dict):
    """发布 Agent 事件"""
    from app.services.event_bus import get_event_bus
    task_id = state.get("trace_id", "")
    if not task_id:
        return
    event_bus = get_event_bus()
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **data}
    asyncio.ensure_future(event_bus.publish(task_id, event_type, payload))
```

**精确 Hook 点**:

| 节点函数 | 行号 | 插入代码 | 事件 |
|---------|------|---------|------|
| `user_input_node` | L77 前 | `_emit_node(state, "user_input")` | supervisor_node |
| `intent_recognition_node` | L109 前 | `_emit_node(state, "intent_recognition")` (含 intent 数据) | supervisor_node |
| `task_planner_node` | L161 前 | `_emit_node(state, "task_planner")` (含 tasks 摘要) | supervisor_node |
| `agent_router_node` | L179 后 (task["status"]="running") | `_emit_agent_event(state, "agent_start", {...})` | agent_start |
| `agent_router_node` | L184 后 (execute 前) | 不变 — 事件在 agent_complete 时发布 | — |
| `agent_router_node` | L196 前 | `_emit_agent_event(state, "agent_complete", {...})` | agent_complete |
| `agent_router_node` | L186 except 块 | `_emit_agent_event(state, "agent_error", {...})` | agent_error |
| `result_validator_node` | L209 前 | `_emit_node(state, "result_validator")` | supervisor_node |
| `result_aggregator_node` | L239 前 | `_emit_node(state, "result_aggregator")` | supervisor_node |
| `final_response_node` | L255 前 | `_emit_node(state, "finalize_response")` | supervisor_node |

**关键**: 事件发布使用 `asyncio.ensure_future()` 而非 `await` — 不阻塞节点执行。

### 3.4 `backend/app/api/v1/__init__.py` (+3 行)

```python
from app.api.v1 import agent, task, trace, auth, dashboard, health, business, stream  # P3

router.include_router(stream.router, tags=["Stream"])  # P3
```

### 3.5 `backend/app/schemas/agent.py` (+8 行)

```python
# P3: ChatResponse 新增字段
class ChatResponse(BaseModel):
    task_id: str
    conversation_id: str
    status: str
    response: Optional[str] = None
    agents_used: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
    execution_time_ms: Optional[int] = None
    stream_url: Optional[str] = None  # P3: SSE 流地址 (streaming_enabled=true 时)
```

---

## 4. Frontend 详细设计

### 4.1 `frontend/src/app/agent/chat/page.tsx` (~200 行修改)

**删除内容** (fake setTimeout 动画, line 84-112):

```typescript
// === 删除: Phase 1-3 假动画 (lines 84-112) ===
const phase1Agents: AgentStatus[] = DEFAULT_AGENTS.map(...)  // ❌ 删除
setAgents(phase1Agents);                                      // ❌ 删除
await new Promise((r) => setTimeout(r, 800));                 // ❌ 删除
setAgents((prev) => prev.map(...phase 2...))                  // ❌ 删除
await new Promise((r) => setTimeout(r, 600));                 // ❌ 删除
setAgents((prev) => prev.map(...phase 3...))                  // ❌ 删除
```

**新增内容** (SSE 事件驱动):

```typescript
const handleSend = useCallback(async () => {
  if (!input.trim() || loading) return;
  
  const userMsg: Message = { role: "user", content: input };
  setMessages(prev => [...prev, userMsg]);
  setInput("");
  setLoading(true);
  
  // P3: 重置 Agent 面板
  setAgents(DEFAULT_AGENTS.map(a => ({ ...a, status: "pending", action: "待命中" })));
  
  try {
    const res = await apiFetch(`${API}/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMsg.content }),
    });
    const data = await res.json();
    
    // P3 分支: streaming 模式
    if (data.stream_url) {
      const es = new EventSource(`${API}${data.stream_url}`);
      
      es.addEventListener("node_complete", (e) => {
        const { node } = JSON.parse(e.data);
        if (node === "intent_recognition") {
          setAgents(prev => prev.map(a => 
            a.name === "Supervisor" ? { ...a, status: "running", action: "意图识别完成" } : a
          ));
        } else if (node === "task_planner") {
          setAgents(prev => prev.map(a =>
            a.name === "Supervisor" ? { ...a, status: "completed", action: "✅ 任务规划完成", duration: "0.5s" } : a
          ));
        }
      });
      
      es.addEventListener("agent_start", (e) => {
        const { agent } = JSON.parse(e.data);
        setAgents(prev => prev.map(a =>
          a.name === agent ? { ...a, status: "running", action: "执行中..." } : a
        ));
      });
      
      es.addEventListener("agent_done", (e) => {
        const { agent, summary, execution_time_ms } = JSON.parse(e.data);
        setAgents(prev => prev.map(a => a.name === agent ? {
          ...a, status: "completed" as const,
          action: summary?.slice(0, 50) || "✅ 完成",
          duration: `${((execution_time_ms || 0) / 1000).toFixed(1)}s`,
        } : a));
      });
      
      es.addEventListener("agent_error", (e) => {
        const { agent, error } = JSON.parse(e.data);
        setAgents(prev => prev.map(a => a.name === agent ? {
          ...a, status: "failed" as const, action: `❌ ${error?.slice(0, 40)}`,
        } : a));
      });
      
      es.addEventListener("done", (e) => {
        const { final_response, agents_used, task_id } = JSON.parse(e.data);
        setMessages(prev => [...prev, {
          role: "assistant", content: final_response,
          agents: agents_used, taskId: task_id,
        }]);
        setLoading(false);
        es.close();
      });
      
      es.onerror = () => { setLoading(false); es.close(); };
      return;
    }
    
    // === v1.2 兼容: 同步模式 (streaming disabled) ===
    // 保留原有逻辑: 一次性显示结果
    const aiMsg: Message = {
      role: "assistant",
      content: data.response || "处理完成",
      agents: data.agents_used,
      traceId: data.trace_id,
      taskId: data.task_id,
    };
    setMessages(prev => [...prev, aiMsg]);
    setAgents(DEFAULT_AGENTS);
    setLoading(false);
    
  } catch {
    setMessages(prev => [...prev, { role: "assistant", content: "服务暂不可用" }]);
    setLoading(false);
  }
}, [input, loading]);
```

### 4.2 `frontend/src/components/agent-trace/DAGView.tsx` (~80 行修改)

**策略**: 不新建组件。在现有 DAGView 增加 `live` prop，`live=true` 时连接 SSE 实时更新 DAG。

```typescript
// DAGView.tsx — P3 改造

interface DAGViewProps {
  taskId?: string;
  live?: boolean;  // P3: 实时模式
}

export default function AgentTraceDAG({ taskId, live = false }: DAGViewProps) {
  const [dag, setDag] = useState(...);
  const [selectedNode, setSelectedNode] = useState<DAGNode | null>(null);
  const [loading, setLoading] = useState(Boolean(taskId));
  
  // P3: live 模式 — SSE 实时更新
  useEffect(() => {
    if (!live || !taskId) return;
    const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
    const es = new EventSource(`${API}/agent/stream/${taskId}`);
    
    // 初始化空 DAG
    setDag({ nodes: [
      { id: "user", label: "用户需求", type: "user", status: "completed", x: 360, y: 20 },
      { id: "supervisor", label: "Supervisor", type: "supervisor", status: "running", x: 360, y: 120 },
    ], edges: [{ from: "user", to: "supervisor" }] });
    
    es.addEventListener("node_complete", (e) => {
      const { node } = JSON.parse(e.data);
      setDag(prev => ({
        ...prev,
        nodes: prev.nodes.map(n => 
          n.id === "supervisor" ? { ...n, action: node, status: "running" } : n
        ),
      }));
    });
    
    es.addEventListener("agent_start", (e) => {
      const { agent, display } = JSON.parse(e.data);
      const y = 240 + prev.nodes.filter(n => n.type === "agent").length * 130;
      setDag(prev => ({
        nodes: [...prev.nodes, {
          id: agent, label: agent, type: "agent", agent: display,
          status: "running", x: 360, y,
        }],
        edges: [...prev.edges, { from: "supervisor", to: agent }],
      }));
    });
    
    es.addEventListener("agent_done", (e) => {
      const { agent, summary } = JSON.parse(e.data);
      setDag(prev => ({
        ...prev,
        nodes: prev.nodes.map(n =>
          n.id === agent ? { ...n, status: "completed", output: summary } : n
        ),
      }));
    });
    
    es.addEventListener("done", () => {
      setDag(prev => ({
        ...prev,
        nodes: [
          ...prev.nodes.map(n => n.id === "supervisor" ? { ...n, status: "completed" } : n),
          { id: "result", label: "最终报告", type: "result", status: "completed", x: 360,
            y: Math.max(...prev.nodes.filter(n => n.type === "agent").map(n => n.y), 240) + 130 },
        ],
        edges: [
          ...prev.edges,
          ...prev.nodes.filter(n => n.type === "agent" && n.status === "completed").map(n => ({ from: n.id, to: "result" })),
        ],
      }));
      es.close();
    });
    
    return () => es.close();
  }, [live, taskId]);
  
  // [v1.2 逻辑: 非 live 时保留原有 fetch trace 行为]
  useEffect(() => {
    if (live || !taskId) return;
    // ... 原有 fetch /agent/task/{id}/trace 逻辑不变 ...
  }, [taskId, live]);
  
  // [渲染逻辑不变]
}
```

---

## 5. 事件流全链路 (STREAMING_ENABLED=true)

```
POST /api/v1/agent/chat
  → 立即返回 { task_id, stream_url, status: "processing" }
  → asyncio.create_task(execute_graph_with_events(...))

后台执行:
  graph.ainvoke(state, config)
    │
    ├─ user_input_node        → EventBus.publish("supervisor_node", {node:"user_input"})
    │                            → EventNormalizer.normalize → SSE: node_complete
    │
    ├─ intent_recognition_node → EventBus.publish("supervisor_node", {node:"intent_recognition"})
    │                            → SSE: node_complete
    │
    ├─ task_planner_node      → EventBus.publish("supervisor_node", {node:"task_planner"})
    │                            → SSE: node_complete
    │
    ├─ agent_router_node (1/2)
    │   ├─ EventBus.publish("agent_start", {agent:"RiskAgent",...})
    │   │   → SSE: agent_start
    │   ├─ execute_business_agent("RiskAgent", ...)
    │   └─ EventBus.publish("agent_complete", {agent:"RiskAgent",...})
    │       → SSE: agent_done
    │
    ├─ agent_router_node (2/2)
    │   ├─ EventBus.publish("agent_start", {agent:"PolicyAgent",...})
    │   └─ EventBus.publish("agent_complete", {...})
    │
    ├─ result_validator_node  → SSE: node_complete
    ├─ result_aggregator_node → SSE: node_complete
    └─ final_response_node     → SSE: node_complete

  execute_graph_with_events 完成:
    → EventBus.publish("done", {...}) → SSE: done
    → db_tool.save_agent_task(...)
    → db_tool.save_message(...)
```

**前端 SSE 消费者**:
```
EventSource("/api/v1/agent/stream/T-001")
  ├─ snapshot      → 初始化 DAG 状态 (重连场景)
  ├─ node_complete → 更新 Supervisor 节点进度
  ├─ agent_start   → Agent 面板: running
  ├─ agent_done    → Agent 面板: completed + summary
  ├─ agent_error   → Agent 面板: failed + error
  └─ done          → 显示最终回复, 关闭 EventSource
```

---

## 6. 兼容性矩阵

| 配置 | POST /agent/chat 行为 | GET /agent/stream/{id} | Frontend 行为 |
|------|----------------------|----------------------|--------------|
| `STREAMING_ENABLED=true` | 异步, 立即返回 | SSE 事件流 | EventSource 事件驱动 |
| `STREAMING_ENABLED=false` | 同步, 等待完成 | 404 | REST fetch 等待 (v1.2 行为) |

**`DATABASE_ENABLED=false` 兼容**: P3 不增删 DB 操作。所有 DB 调用沿用 P2 DatabaseTool，自动静默跳过。

---

## 7. 文件变更清单

| # | 文件 | 操作 | 行数 | 依赖 |
|---|------|------|------|------|
| 1 | `app/services/event_bus.py` | **新建** | ~100 | 无 |
| 2 | `app/services/event_normalizer.py` | **新建** | ~80 | 无 |
| 3 | `app/services/stream_executor.py` | **新建** | ~60 | event_bus, database_tool |
| 4 | `app/api/v1/stream.py` | **新建** | ~100 | event_bus, event_normalizer, graph |
| 5 | `app/config.py` | 修改 | +3 | 无 |
| 6 | `app/schemas/agent.py` | 修改 | +3 | 无 |
| 7 | `app/api/v1/agent.py` | 修改 | +20/-10 | stream_executor |
| 8 | `app/api/v1/__init__.py` | 修改 | +2 | stream |
| 9 | `app/langgraph/nodes/supervisor_nodes.py` | 修改 | +35/-0 | event_bus |
| 10 | `frontend/src/app/agent/chat/page.tsx` | 修改 | +120/-90 | 无 |
| 11 | `frontend/src/components/agent-trace/DAGView.tsx` | 修改 | +80/+10 | 无 |
| 12 | `frontend/src/app/agent/trace/[taskId]/page.tsx` | 修改 | +5 | DAGView live prop |
| **合计** | **12 文件** | | **~550** | |

---

## 8. 验收清单

- [ ] `STREAMING_ENABLED=false` → POST /agent/chat 同步返回 (v1.2 行为)
- [ ] `STREAMING_ENABLED=false` → GET /agent/stream/{id} 返回 404
- [ ] `STREAMING_ENABLED=true` → POST /agent/chat 立即返回 (status=processing)
- [ ] `STREAMING_ENABLED=true` → GET /agent/stream/{id} SSE 连接成功
- [ ] SSE 事件流包含: node_complete × 7, agent_start/agent_done × N, done
- [ ] EventNormalizer 正确映射所有事件类型
- [ ] Frontend Agent 面板无 setTimeout 假延迟
- [ ] Frontend DAGView live 模式实时更新节点
- [ ] DAGView 非 live 模式仍可用 (向后兼容 trace 页面)
- [ ] 断线重连时 snapshot 事件恢复当前状态
- [ ] agent_error 事件前端正确展示
- [ ] Chrome DevTools Network 面板可观察 SSE text/event-stream
- [ ] P0/P1/P2 所有现有测试通过
- [ ] EventBus Queue 满时丢弃最早事件 + 打印 warning

---

*Generated by Hermes Agent · 2026-07-25 · P3 Streaming Implementation Plan V1.0*
