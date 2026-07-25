# WebSocket / SSE Streaming Architecture V1.0

> **P3 Real-Time Agent Execution Streaming**  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-25  
> **前置**: P0 Enterprise Data ✅ | P1 Policy RAG ✅ | P2 Checkpointer ✅

---

## 目录

1. [当前 REST 模式问题分析](#1-当前-rest-模式问题分析)
2. [Streaming 架构决策](#2-streaming-架构决策)
3. [FastAPI SSE 设计方案](#3-fastapi-sse-设计方案)
4. [WebSocket 设计方案（备选）](#4-websocket-设计方案备选)
5. [Supervisor 事件发布机制](#5-supervisor-事件发布机制)
6. [LangGraph Node Event Mapping](#6-langgraph-node-event-mapping)
7. [Agent 执行实时状态](#7-agent-执行实时状态)
8. [Frontend React 接收方案](#8-frontend-react-接收方案)
9. [Trace UI 实时更新方案](#9-trace-ui-实时更新方案)
10. [错误恢复机制](#10-错误恢复机制)

---

## 1. 当前 REST 模式问题分析

### 1.1 当前调用链路

```
用户输入 "分析广州数控风险并匹配政策"
  │
  ├─ POST /api/v1/agent/chat  { message: "..." }
  │     │
  │     ├─ await get_supervisor_graph()               [~0ms]
  │     ├─ graph.ainvoke(state, config)                [总耗时: 15-60s]
  │     │     ├─ user_input_node          [~1ms]
  │     │     ├─ intent_recognition_node  [LLM, ~2s]
  │     │     ├─ task_planner_node        [~1ms]
  │     │     ├─ agent_router_node × 2    [RiskAgent ~5s + PolicyAgent ~3s]
  │     │     │     └─ execute_business_agent()  ← 同步阻塞 .invoke()
  │     │     ├─ result_validator_node    [~1ms]
  │     │     ├─ result_aggregator_node   [LLM, ~2s]
  │     │     └─ final_response_node      [~1ms]
  │     │
  │     └─ 返回 ChatResponse { response, agents_used, trace_id }
  │
  └─ 前端等待 15-60 秒后才显示结果
```

### 1.2 问题清单

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | **黑盒等待** — 用户看到空白/loading 15-60 秒 | 🔴 高 | 体验极差，用户以为系统卡死 |
| 2 | **假动画** — 前端用 `setTimeout(800ms)` 模拟 Agent 进度 | 🔴 高 | 与实际执行完全脱节，状态造假 |
| 3 | **无中间反馈** — Supervisor 7 个 node 执行进度不可见 | 🟡 中 | 用户不知道"进行到哪了" |
| 4 | **Agent 执行不可见** — 每个 Agent 的 tool 调用完全黑盒 | 🟡 中 | 管理员无法监控 Agent 行为 |
| 5 | **Trace 只能事后看** — `GET /agent/task/{id}/trace` 等任务完成后才有数据 | 🟡 中 | 实时调试不可能 |
| 6 | **LLM 流式输出不可用** — LLM Gateway 有 token-by-token 能力但被埋没 | 🟢 低 | 用户想看到 AI 逐字生成 |

### 1.3 当前代码证据

```typescript
// frontend/src/app/agent/chat/page.tsx:85-112 — 完全虚假的 Agent 动画
const phase1Agents = DEFAULT_AGENTS.map(...phase 1 fake...)
await new Promise((r) => setTimeout(r, 800));  // ← 假延迟
setAgents(prev => prev.map(...phase 2 fake...))
await new Promise((r) => setTimeout(r, 600));  // ← 假延迟
```

```python
# backend/app/agents/executor.py:61 — 同步阻塞调用
raw = get_investment_graph().invoke({...})  # ← 完全阻塞，无法发送事件
```

---

## 2. Streaming 架构决策

### 2.1 方案对比

| 维度 | SSE (Server-Sent Events) | WebSocket |
|------|--------------------------|-----------|
| 协议 | HTTP/1.1 长连接 | 独立协议 (ws://) |
| 方向 | 单向: Server → Client | 双向: Server ↔ Client |
| 复杂度 | 低 (标准 EventSource API) | 中 (需要 ws 库) |
| 负载均衡 | HTTP 原生支持 | 需要 sticky session |
| Docker/代理 | 无需特殊配置 | 需要 WebSocket 升级 |
| 重连 | 浏览器自动 | 需手动实现 |
| 适合场景 | 实时推送、进度更新 | 双向交互、低延迟 |

### 2.2 决策: SSE 为主，WebSocket 备选

**选择 SSE 的原因:**

1. **单向就够了** — 用户通过 REST POST 提交任务（已有），只需 Server→Client 推送进度
2. **浏览器原生支持** — `EventSource` API 自动重连，比 WebSocket 更少的自定义代码
3. **HTTP 基础设施兼容** — Nginx/Docker/负载均衡无需特殊配置
4. **LangGraph astream_events** — LangGraph 原生支持 async generator 事件流，天然适配 SSE
5. **够轻量** — 不需要引入 `websockets` 库，FastAPI 的 `StreamingResponse` 即可

### 2.3 混合架构

```
用户发送消息
  │
  ├─ POST /api/v1/agent/chat     → 返回 { task_id, stream_url }
  │
  └─ 前端连接 GET /api/v1/agent/stream/{task_id}  (SSE)
       │
       ├─ event: supervisor_node   → 当前 Supervisor 节点
       ├─ event: agent_start       → Agent 开始执行
       ├─ event: agent_progress    → Agent 工具调用详情
       ├─ event: agent_complete    → Agent 执行完成
       ├─ event: llm_token         → LLM 流式 token (可选)
       └─ event: done              → 任务完成，包含最终结果
```

**为什么不是 WebSocket?**

当前需求不需要 Client→Server 推送（用户无需中途打断/修改任务）。如果未来需要"用户中途插话修改任务"或"Agent 请求用户确认"，再升级到 WebSocket。

### 2.4 架构约束（必须保持）

```
User  →  FastAPI Gateway  →  Supervisor  →  Agent  →  Tool Gateway
 ↑                              │               │           │
 └── SSE 事件流 ←── EventBus ←──┘               │           │
                                  └── EventBus ──┘           │
                                               └── EventBus ─┘
```

- **不改变 Supervisor 7 节点架构** — 仅在每个节点返回前发送事件
- **不改变 Agent 接口** — `execute_business_agent()` 签名不变
- **不直接访问数据库** — 持久化通过 DatabaseTool（P2 已建立）
- **Mock 模式兼容** — `STREAMING_ENABLED=false` 时降级为当前 REST 行为

---

## 3. FastAPI SSE 设计方案

### 3.1 端点设计

```python
# backend/app/api/v1/stream.py (新建)

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json, asyncio

router = APIRouter()


@router.get("/agent/stream/{task_id}")
async def agent_stream(task_id: str):
    """SSE 端点：订阅 Agent 执行实时事件流"""
    from app.services.event_bus import get_event_bus
    
    event_bus = get_event_bus()
    queue: asyncio.Queue = asyncio.Queue()
    
    # 订阅此 task_id 的事件
    await event_bus.subscribe(task_id, queue)
    
    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"event: {event['type']}\n"
                    yield f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                    
                    if event['type'] == 'done' or event['type'] == 'error':
                        break
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {{}}\n\n"
        finally:
            await event_bus.unsubscribe(task_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )
```

### 3.2 Agent Chat 改造

```python
# backend/app/api/v1/agent.py — 修改 agent_chat

@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid4())
    task_id = str(uuid4())
    
    # ... 原有逻辑 (历史加载、conversation 保存) ...
    
    # P3: 改为异步流式执行 (不阻塞 HTTP 响应)
    asyncio.create_task(_execute_and_stream(
        task_id=task_id,
        conversation_id=conversation_id,
        state=state,
        config=config,
        db_tool=db_tool,
        user_message=request.message,
    ))
    
    # 立即返回 task_id + stream_url
    return ChatResponse(
        task_id=task_id,
        conversation_id=conversation_id,
        status="processing",
        response=None,
        stream_url=f"/api/v1/agent/stream/{task_id}",  # P3 新增
    )
```

**关键变化**: `POST /agent/chat` 不再等待执行完成 — 立即返回，后台执行，前端通过 SSE 接收结果。

### 3.3 EventBus 核心

```python
# backend/app/services/event_bus.py (新建)

"""EventBus — P3 事件发布/订阅总线

设计原则:
  - 基于 asyncio.Queue 的内存实现 (无需 Redis，够轻量)
  - 每个 task_id 独立 channel
  - 多订阅者支持 (WebSocket + SSE 可共存)
  - Mock 模式兼容: STREAMING_ENABLED=false 时降级

约束:
  - 不改变 Supervisor 架构
  - 不改变 Agent 接口
  - 仅通过 publish() 发送事件，不直接访问数据库
"""

import asyncio
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._subscriptions: Dict[str, List[asyncio.Queue]] = {}

    async def subscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        if task_id not in self._subscriptions:
            self._subscriptions[task_id] = []
        self._subscriptions[task_id].append(queue)
        logger.debug(f"[EventBus] subscribe {task_id} (total: {len(self._subscriptions[task_id])})")

    async def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        if task_id in self._subscriptions:
            self._subscriptions[task_id].remove(queue)
            if not self._subscriptions[task_id]:
                del self._subscriptions[task_id]

    async def publish(self, task_id: str, event_type: str, data: dict) -> None:
        """发布事件到所有订阅者"""
        event = {"type": event_type, "data": data}
        queues = self._subscriptions.get(task_id, [])
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"[EventBus] queue full for {task_id}, dropping event {event_type}")


# 全局单例
_event_bus: EventBus = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
```

---

## 4. WebSocket 设计方案（备选）

### 4.1 端点设计

```python
# backend/app/api/v1/ws.py (备选，P3 不实现)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/agent/ws/{task_id}")
async def agent_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()
    
    event_bus = get_event_bus()
    queue = asyncio.Queue()
    await event_bus.subscribe(task_id, queue)
    
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event['type'] in ('done', 'error'):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await event_bus.unsubscribe(task_id, queue)
```

### 4.2 升级时机

如果未来出现以下需求，从 SSE 迁移到 WebSocket：

- 用户需要在 Agent 执行中途"打断"或"修改指令" (Client→Server)
- 需要双向心跳保活 (Server 主动检测客户端存活)
- 延迟要求 < 100ms (WebSocket 比 SSE 逐行解析更快)

当前场景不需要，P3 仅实现 SSE。

---

## 5. Supervisor 事件发布机制

### 5.1 发布点：在每个 node 返回前发送事件

```python
# backend/app/langgraph/nodes/supervisor_nodes.py — 改造模式

def user_input_node(state: SupervisorState) -> SupervisorState:
    # ... 原有逻辑 ...
    
    # P3: 发布事件
    _emit_node_event(state, "user_input", {"status": "running"})
    
    # ... 原有逻辑 ...
    return state


def agent_router_node(state: SupervisorState) -> SupervisorState:
    # ... 原有逻辑 ...
    
    task = task_plan[idx]
    
    # P3: 发布 agent_start 事件
    _emit_agent_event(state, "agent_start", {
        "agent": task["agent"],
        "display": AGENT_REGISTRY.get(task["agent"], {}).get("display", task["agent"]),
        "task_id": task["task_id"],
        "intent": task["intent"],
    })
    
    try:
        result = execute_business_agent(agent, task, state)
    except Exception as exc:
        # P3: 发布 agent_error 事件
        _emit_agent_event(state, "agent_error", {
            "agent": task["agent"],
            "error": str(exc),
        })
        ...
    
    # P3: 发布 agent_complete 事件
    _emit_agent_event(state, "agent_complete", {
        "agent": task["agent"],
        "status": "completed",
        "summary": result.get("result", {}).get("summary", ""),
        "execution_time_ms": result.get("execution_time_ms", 0),
    })
    
    state["agent_results"][agent] = result
    task["status"] = "completed" if result["status"] == "success" else "failed"
    return state
```

### 5.2 事件发布辅助函数

```python
# 在 supervisor_nodes.py 中新增

def _emit_node_event(state: SupervisorState, node_name: str, extra: dict = None):
    """发布 Supervisor 节点事件"""
    from app.services.event_bus import get_event_bus
    task_id = state.get("trace_id", "")
    if not task_id:
        return
    event_bus = get_event_bus()
    data = {"node": node_name, "timestamp": datetime.now(timezone.utc).isoformat(), **(extra or {})}
    asyncio.ensure_future(event_bus.publish(task_id, "supervisor_node", data))


def _emit_agent_event(state: SupervisorState, event_type: str, extra: dict = None):
    """发布 Agent 执行事件"""
    from app.services.event_bus import get_event_bus
    task_id = state.get("trace_id", "")
    if not task_id:
        return
    event_bus = get_event_bus()
    data = {"timestamp": datetime.now(timezone.utc).isoformat(), **(extra or {})}
    asyncio.ensure_future(event_bus.publish(task_id, event_type, data))


def _emit_llm_token(state: SupervisorState, token: str):
    """发布 LLM 流式 token"""
    from app.services.event_bus import get_event_bus
    task_id = state.get("trace_id", "")
    if not task_id:
        return
    event_bus = get_event_bus()
    asyncio.ensure_future(event_bus.publish(task_id, "llm_token", {"token": token}))
```

**关键**: 使用 `asyncio.ensure_future()` 而非 `await` — 事件发送不阻塞节点执行。丢失事件不影响 Agent 正确性。

---

## 6. LangGraph Node Event Mapping

### 6.1 7 节点 → 事件类型映射

| Node | Event Type | 关键数据 | 发布时机 |
|------|-----------|---------|---------|
| `user_input` | `supervisor_node` | `{node: "user_input", status: "running"}` | node 完成前 |
| `intent_recognition` | `supervisor_node` | `{node: "intent_recognition", intent, intents, confidence}` | LLM 返回后 |
| `task_planner` | `supervisor_node` | `{node: "task_planner", tasks: [{agent, intent}]}` | plan 生成后 |
| `agent_router` (entry) | `agent_start` | `{agent, display, task_id, intent}` | 每个 task 开始前 |
| `agent_router` (exit) | `agent_complete` | `{agent, status, summary, execution_time_ms}` | 每个 task 完成后 |
| `agent_router` (error) | `agent_error` | `{agent, error}` | Agent 执行失败 |
| `result_validator` | `supervisor_node` | `{node: "result_validator", has_failures}` | 验证后 |
| `result_aggregator` | `supervisor_node` | `{node: "result_aggregator"}` | LLM 聚合前 |
| `result_aggregator` | `llm_token` | `{token: "..."}` | LLM 流式输出每个 token |
| `finalize_response` | `supervisor_node` | `{node: "finalize_response", status: "completed"}` | 完成前 |
| (graph END) | `done` | `{task_id, status, final_response, agents_used}` | graph 执行完成后 |

### 6.2 完整事件流示例

```
POST /api/v1/agent/chat { message: "分析广州数控风险并匹配政策" }
  → { task_id: "T-001", stream_url: "/api/v1/agent/stream/T-001" }

连接 GET /api/v1/agent/stream/T-001

event: supervisor_node
data: {"node":"user_input","timestamp":"..."}

event: supervisor_node
data: {"node":"intent_recognition","intent":"risk_single","intents":["risk_single","policy_match"],"confidence":0.9}

event: supervisor_node
data: {"node":"task_planner","tasks":[{"agent":"RiskAgent","intent":"risk_single"},{"agent":"PolicyAgent","intent":"policy_match"}]}

event: agent_start
data: {"agent":"RiskAgent","display":"企业风险雷达","task_id":"T-001-0","intent":"risk_single"}

event: agent_complete
data: {"agent":"RiskAgent","status":"completed","summary":"广州数控风险评分 28，等级 LOW","execution_time_ms":5200}

event: agent_start
data: {"agent":"PolicyAgent","display":"AI政策顾问","task_id":"T-001-1","intent":"policy_match"}

event: agent_complete
data: {"agent":"PolicyAgent","status":"completed","summary":"匹配 5 条政策：广东省机器人产业发展专项资金...","execution_time_ms":3100}

event: supervisor_node
data: {"node":"result_validator"}

event: supervisor_node
data: {"node":"result_aggregator"}

event: llm_token
data: {"token":"##"}

event: llm_token
data: {"token":" 广州"}

... (token by token)

event: done
data: {"task_id":"T-001","status":"completed","final_response":"## 广州数控风险分析报告\n...","agents_used":["RiskAgent","PolicyAgent"]}
```

---

## 7. Agent 执行实时状态

### 7.1 Agent 状态机

```
pending → running → completed
        → running → failed
```

### 7.2 Agent 进度上报（executor.py 改造）

```python
# backend/app/agents/executor.py — P3 改造

def execute_business_agent(agent_name: str, task: dict, 
                           supervisor_state: dict) -> dict:
    started = time.perf_counter()
    task_id = task["task_id"]
    
    # P3: 发布 agent_progress 事件（在每个 tool 调用前后）
    # 方法: 在 Agent graph invoke 前后注入 callback
    ...
    
    elapsed_ms = max(1, int((time.perf_counter() - started) * 1000))
    result = { ... }
    
    # P3: agent_complete 事件由 agent_router_node 统一发布
    # 这里不重复发布，保持单一职责
    
    return result
```

### 7.3 Agent 内部 Tool 调用事件（可选，P3 阶段可简化）

如果需要在 Agent 内部级的 tool 调用可见性，可以通过 LangGraph 的 `astream_events` 或自定义 callback：

```python
# 方案 A: 使用 LangGraph astream_events（推荐）
async for event in graph.astream_events(state, config, version="v2"):
    if event["event"] == "on_tool_start":
        await event_bus.publish(task_id, "agent_tool_start", {
            "agent": agent_name, "tool": event["name"], "input": event["data"].get("input")
        })
    elif event["event"] == "on_tool_end":
        await event_bus.publish(task_id, "agent_tool_end", {
            "agent": agent_name, "tool": event["name"], "output": event["data"].get("output")
        })
```

**P3 决策**: agent_internal tool 调用事件作为可选增强，先实现 supervisor 层级和 agent_start/complete，后续迭代补充。

---

## 8. Frontend React 接收方案

### 8.1 当前假动画 → 替换为 SSE 真实事件

```typescript
// frontend/src/hooks/useAgentStream.ts (新建)

import { useState, useEffect, useCallback } from "react";

interface StreamEvent {
  type: "supervisor_node" | "agent_start" | "agent_complete" | 
        "agent_error" | "llm_token" | "done" | "heartbeat";
  data: Record<string, any>;
}

export function useAgentStream(taskId: string | null) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [finalResponse, setFinalResponse] = useState<string | null>(null);
  const [status, setStatus] = useState<"connecting" | "streaming" | "done" | "error">("connecting");

  useEffect(() => {
    if (!taskId) return;

    const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
    const url = `${API}/agent/stream/${taskId}`;
    
    const eventSource = new EventSource(url);
    
    eventSource.addEventListener("supervisor_node", (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: "supervisor_node", data }]);
      setStatus("streaming");
    });
    
    eventSource.addEventListener("agent_start", (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: "agent_start", data }]);
    });
    
    eventSource.addEventListener("agent_complete", (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: "agent_complete", data }]);
    });
    
    eventSource.addEventListener("agent_error", (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: "agent_error", data }]);
    });
    
    eventSource.addEventListener("llm_token", (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: "llm_token", data }]);
      // 流式拼接最终回复
      setFinalResponse(prev => (prev || "") + data.token);
    });
    
    eventSource.addEventListener("done", (e) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type: "done", data }]);
      setFinalResponse(data.final_response);
      setStatus("done");
      eventSource.close();
    });
    
    eventSource.onerror = () => {
      setStatus("error");
      eventSource.close();
    };
    
    return () => eventSource.close();
  }, [taskId]);

  return { events, finalResponse, status };
}
```

### 8.2 Chat 页面改造

```typescript
// frontend/src/app/agent/chat/page.tsx — P3 改造

const handleSend = useCallback(async () => {
  if (!input.trim() || loading) return;
  
  const userMsg: Message = { role: "user", content: input };
  setMessages(prev => [...prev, userMsg]);
  setInput("");
  setLoading(true);
  
  try {
    // P3: POST 立即返回，不等待执行完成
    const res = await apiFetch(`${API}/agent/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMsg.content }),
    });
    const { task_id, stream_url } = await res.json();
    
    // P3: 连接到 SSE 流
    const eventSource = new EventSource(`${API}${stream_url}`);
    
    // 动态更新 Agent 面板
    eventSource.addEventListener("agent_start", (e) => {
      const { agent } = JSON.parse(e.data);
      setAgents(prev => prev.map(a => 
        a.name === agent ? { ...a, status: "running", action: "执行中..." } : a
      ));
    });
    
    eventSource.addEventListener("agent_complete", (e) => {
      const { agent, summary, execution_time_ms } = JSON.parse(e.data);
      setAgents(prev => prev.map(a => 
        a.name === agent ? { 
          ...a, status: "completed", 
          action: summary?.slice(0, 50) || "✅ 完成",
          duration: `${(execution_time_ms / 1000).toFixed(1)}s`
        } : a
      ));
    });
    
    eventSource.addEventListener("done", (e) => {
      const { final_response, agents_used } = JSON.parse(e.data);
      setMessages(prev => [...prev, {
        role: "assistant",
        content: final_response,
        agents: agents_used,
        taskId: task_id,
      }]);
      setLoading(false);
      eventSource.close();
    });
    
    eventSource.onerror = () => {
      setLoading(false);
      eventSource.close();
    };
    
  } catch {
    setMessages(prev => [...prev, { role: "assistant", content: "服务暂不可用" }]);
    setLoading(false);
  }
}, [input, loading]);
```

### 8.3 改动对比

| 组件 | 当前 (v1.1) | P3 |
|------|-----------|-----|
| agent_chat 定时机制 | `setTimeout(800)` 假延迟 | SSE 真实事件驱动 |
| Agent 状态面板 | 硬编码 3 阶段动画 | `agent_start`/`agent_complete` 事件更新 |
| 消息显示时机 | 15-60s 后一次性显示 | `done` 事件后显示（或 llm_token 流式显示） |
| 错误处理 | catch 后显示 "服务暂不可用" | `agent_error` 事件 + 具体错误信息 |

---

## 9. Trace UI 实时更新方案

### 9.1 当前 Trace 页面

```typescript
// frontend/src/app/agent/trace/[taskId]/page.tsx
// 当前: 在 useEffect 中 fetch GET /agent/task/{id}/trace
// 问题: 只能等任务完成后获取完整 trace

// P3 改造: 使用 useAgentStream hook 订阅实时事件
```

### 9.2 实时 Trace DAG 更新

```typescript
// frontend/src/components/agent-trace/LiveDAGView.tsx (新建)

export default function LiveDAGView({ taskId }: { taskId: string }) {
  const { events, status } = useAgentStream(taskId);
  const [dag, setDag] = useState({ nodes: [], edges: [] });
  
  useEffect(() => {
    // 根据 streaming events 动态构建 DAG
    let nodes = [
      { id: "user", type: "user", status: "completed", ... },
      { id: "supervisor", type: "supervisor", status: "completed", ... },
    ];
    
    for (const event of events) {
      if (event.type === "supervisor_node") {
        // 更新 supervisor 节点状态
      } else if (event.type === "agent_start") {
        nodes.push({
          id: event.data.agent,
          type: "agent",
          status: "running",
          ...
        });
      } else if (event.type === "agent_complete") {
        const node = nodes.find(n => n.id === event.data.agent);
        if (node) node.status = "completed";
      }
    }
    
    setDag({ nodes, edges: buildEdges(nodes, events) });
  }, [events]);
  
  return <DAGCanvas dag={dag} />;
}
```

### 9.3 实时 Trace 体验

```
T=0s:    User → (loading...) — 只显示起始节点
T=2s:    User → Supervisor → (executing...) — intent 识别完成
T=3s:    User → Supervisor → [RiskAgent ⏳, PolicyAgent ⏳] — task_plan 展示
T=8s:    User → Supervisor → [RiskAgent ✅, PolicyAgent ⏳] — RiskAgent 完成
T=11s:   User → Supervisor → [RiskAgent ✅, PolicyAgent ✅] — PolicyAgent 完成
T=13s:   User → Supervisor → [Aggregator] → Result ✅ — 全部完成
```

---

## 10. 错误恢复机制

### 10.1 SSE 断线重连

```typescript
// EventSource 浏览器原生支持自动重连
// 后端需处理重连场景: 客户端重连时，返回当前进度

// 后端改造: GET /agent/stream/{task_id}
// 如果 task 已在执行中 → 先发送 current_state 事件（一次性快照），再继续流
```

### 10.2 任务状态快照（重连时发送）

```python
@router.get("/agent/stream/{task_id}")
async def agent_stream(task_id: str):
    ...
    async def event_generator():
        # P3: 如果 task 已在执行中，先发送快照
        graph = await get_supervisor_graph()
        try:
            state = graph.get_state({"configurable": {"thread_id": task_id}})
            if state and state.values:
                snapshot = _build_snapshot(state.values)
                yield f"event: snapshot\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
        except Exception:
            pass  # task 尚未开始
        
        # 然后继续流
        ...
```

### 10.3 错误事件处理

```typescript
// 前端错误处理

eventSource.addEventListener("agent_error", (e) => {
  const { agent, error } = JSON.parse(e.data);
  // 显示具体 agent 错误，但不中断整体流程
  setAgents(prev => prev.map(a => 
    a.name === agent ? { ...a, status: "failed", action: `❌ ${error}` } : a
  ));
});

eventSource.onerror = () => {
  // 连接级错误
  if (status !== "done") {
    // 3 秒后自动重连 (EventSource 默认行为)
    setStatus("connecting");
  }
};
```

### 10.4 降级策略

```python
# config.py
STREAMING_ENABLED: bool = True  # P3 新增配置
```

**STREAMING_ENABLED=false 时**:
- `POST /agent/chat` 降级为当前同步行为（等待完成后返回）
- `GET /agent/stream/{task_id}` 返回 404
- Frontend 降级为当前 REST 模式（使用 `fetch` 等待响应）
- 与 v1.1 行为 100% 一致

**STREAMING_ENABLED=true 时**:
- `POST /agent/chat` 立即返回
- SSE 端点可用
- Frontend 使用 EventSource

---

## 11. 文件变更预估

| # | 文件 | 操作 | 预估行数 | 类别 |
|---|------|------|---------|------|
| 1 | `app/services/event_bus.py` | **新建** | ~80 | EventBus 核心 |
| 2 | `app/services/stream_executor.py` | **新建** | ~60 | 后台执行 + 事件发布 |
| 3 | `app/api/v1/stream.py` | **新建** | ~80 | SSE 端点 |
| 4 | `app/api/v1/agent.py` | 修改 | +15/-10 | 异步执行 + stream_url |
| 5 | `app/langgraph/nodes/supervisor_nodes.py` | 修改 | +40 | 事件发布钩子 |
| 6 | `app/config.py` | 修改 | +2 | STREAMING_ENABLED |
| 7 | `frontend/src/hooks/useAgentStream.ts` | **新建** | ~100 | SSE Hook |
| 8 | `frontend/src/app/agent/chat/page.tsx` | 修改 | ~150/-100 | 真实事件替换假动画 |
| 9 | `frontend/src/components/agent-trace/LiveDAGView.tsx` | **新建** | ~150 | 实时 Trace |
| **合计** | **9 文件** | | **~600** | |

---

## 12. 验收清单

- [ ] `STREAMING_ENABLED=false` → REST 行为与 v1.1 一致
- [ ] `POST /agent/chat` 立即返回 `{ task_id, stream_url }`
- [ ] `GET /agent/stream/{task_id}` SSE 连接成功
- [ ] `supervisor_node` 事件在每个 node 完成后发送
- [ ] `agent_start`/`agent_complete` 事件在每个 Agent 执行前后发送
- [ ] Frontend Agent 面板由真实事件驱动（不再有 setTimeout 假延迟）
- [ ] SSE 断线后自动重连 + 快照恢复
- [ ] `agent_error` 事件前端正确展示
- [ ] Chrome DevTools Network 面板可观察 SSE 事件流
- [ ] 所有现有 P0/P1/P2 测试通过

---

*Generated by Hermes Agent · 2026-07-25 · WebSocket/SSE Streaming Architecture V1.0*
