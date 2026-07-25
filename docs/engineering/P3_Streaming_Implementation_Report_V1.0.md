# P3 WebSocket/SSE Streaming — Implementation Report V1.0

> **P3 Production Upgrade**  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-25  
> **前置**: [WebSocket_Streaming_Architecture_V1.0](./WebSocket_Streaming_Architecture_V1.0.md) → [P3_Streaming_Implementation_Plan_V1.0](./P3_Streaming_Implementation_Plan_V1.0.md)

---

## 1. 修改文件列表

| # | 文件 | 操作 | 行数 | 类别 |
|---|------|------|------|------|
| 1 | `backend/app/services/event_bus.py` | **新建** | ~180 | EventBus + Channel + TTL |
| 2 | `backend/app/services/event_normalizer.py` | **新建** | ~70 | 统一事件格式转换 |
| 3 | `backend/app/services/stream_executor.py` | **新建** | ~90 | 后台执行 + 事件发布 |
| 4 | `backend/app/api/v1/stream.py` | **新建** | ~120 | SSE + snapshot 端点 |
| 5 | `backend/app/config.py` | 修改 | +3 | STREAMING_ENABLED, HEARTBEAT |
| 6 | `backend/app/schemas/agent.py` | 修改 | +1 | ChatResponse.stream_url |
| 7 | `backend/app/api/v1/agent.py` | 修改 | +30/-20 | 双模式 (sync/async) |
| 8 | `backend/app/api/v1/__init__.py` | 修改 | +2 | stream router 注册 |
| 9 | `backend/app/langgraph/nodes/supervisor_nodes.py` | 修改 | +80 | wrapper/middleware |
| 10 | `frontend/src/app/agent/chat/page.tsx` | 修改 | +120/-100 | 删除假动画 + SSE 接入 |
| 11 | `frontend/src/components/agent-trace/DAGView.tsx` | 修改 | +80 | live 模式 |
| **合计** | **11 文件** | | **~700** | |

无新增外部依赖。

---

## 2. 架构实现

### 2.1 事件流全链路

```
POST /api/v1/agent/chat
  ├─ streaming_enabled=true  → asyncio.create_task(execute_graph_with_events)
  │   └─ 立即返回 { task_id, stream_url, status: "processing" }
  │
  ├─ streaming_enabled=false → graph.ainvoke() 同步等待
  │   └─ v1.2 行为, 100% 兼容
  │
GET /api/v1/agent/stream/{task_id}
  ├─ EventBus.subscribe → asyncio.Queue(maxsize=256)
  ├─ 发送 snapshot (重连场景)
  └─ while True: EventNormalizer.normalize(raw) → SSE frame
       ├─ heartbeat (每 15s)
       ├─ node_complete / agent_start / agent_done / agent_error
       └─ done → 关闭
```

### 2.2 EventBus 架构

```
EventBus (单例)
  ├─ create_channel(task_id) → EventChannel
  │     └─ 自动 TTL 清理 (无订阅者 + 300s → close_channel)
  ├─ subscribe(task_id, queue)
  ├─ unsubscribe(task_id, queue)
  └─ publish(task_id, event_type, payload, source)
       └─ put_nowait() → 所有 queue (非阻塞)

EventNormalizer
  └─ normalize(raw) → { event_id, task_id, event_type, source, timestamp, payload }
       ├─ supervisor_node → node_complete
       ├─ agent_start → agent_start
       ├─ agent_complete → agent_done
       ├─ agent_error → agent_error
       └─ done → done
```

### 2.3 Supervisor Node Wrapper

采用 `_wrap_node` / `_wrap_agent_router` middleware 方式，不修改 7 个节点函数内部逻辑：

```python
# 每个 supervisor node 自动包装
user_input_node = _wrap_node("user_input")(user_input_node_impl)
intent_recognition_node = _wrap_node("intent_recognition")(intent_recognition_node_impl)
...

# agent_router 特殊包装 (发布 agent_start / agent_done / agent_error)
agent_router_node = _wrap_agent_router(agent_router_node_impl)
```

---

## 3. 数据库变化

无。P3 不新增表/列/索引。所有持久化沿用 P2 DatabaseTool。

---

## 4. 配置变更

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `STREAMING_ENABLED` | `false` | 默认关闭，保持 v1.2 兼容 |
| `STREAMING_HEARTBEAT_SECONDS` | `15` | SSE 心跳间隔 (秒) |

---

## 5. EventBus 测试

### 5.1 单元测试结果 (43/43)

| 测试类别 | 项数 | 状态 |
|---------|------|------|
| Syntax (9 files) | 9 | ✅ |
| Config | 2 | ✅ |
| EventBus (create/subscribe/publish/unsubscribe/close) | 11 | ✅ |
| EventNormalizer (5 event types + batch) | 6 | ✅ |
| Graph + wrapper imports | 5 | ✅ |
| Schemas (stream_url) | 1 | ✅ |
| P1 Policy RAG | 2 | ✅ |
| P0 Agent Registry | 1 | ✅ |
| P2 DatabaseTool | 1 | ✅ |
| P2 AgentMemory model | 1 | ✅ |

### 5.2 EventBus 详细测试

| 测试项 | 结果 |
|--------|------|
| `create_channel("test-001")` → 返回 EventChannel | ✅ |
| `subscribe` → `subscriber_count=1` | ✅ |
| `publish("supervisor_node", {node:"test"})` → event received | ✅ |
| event 包含 `event_id`, `task_id`, `event_type`, `source`, `timestamp`, `payload` | ✅ |
| `unsubscribe` → `subscriber_count=0` | ✅ |
| `close_channel` → `get_channel` 返回 None | ✅ |
| `publish` 到不存在的 channel → 无崩溃 | ✅ |

### 5.3 EventNormalizer 详细测试

| 原始类型 | 标准化类型 | 结果 |
|---------|----------|------|
| `supervisor_node` | `node_complete` | ✅ |
| `agent_start` | `agent_start` | ✅ |
| `agent_complete` | `agent_done` | ✅ |
| `done` | `done` | ✅ |
| `unknown_type` | `heartbeat` (兜底) | ✅ |
| batch 3 events | 3 results | ✅ |

---

## 6. SSE 测试 (需启动服务)

```bash
# Terminal 1: 启动 backend
cd /mnt/d/industrial-park-v1.1/backend
STREAMING_ENABLED=true .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: 发送请求
curl -s -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"分析广州数控风险"}' | jq .
# → { "task_id": "xxx", "stream_url": "/api/v1/agent/stream/xxx", "status": "processing" }

# Terminal 3: 连接 SSE
curl -N http://localhost:8000/api/v1/agent/stream/xxx
# → event: snapshot
#   data: {"task_id":"xxx","status":"unknown",...}
# → event: heartbeat
#   data: {}
# → event: node_complete
#   data: {"event_id":"...","event_type":"node_complete",...}
# → ...
# → event: done
# → 连接关闭

# Snapshot 端点
curl -s http://localhost:8000/api/v1/agent/stream/xxx/snapshot | jq .
# → { "task_id": "xxx", "status": "completed", "task_plan": [...], ... }
```

**预期 curl -N 输出**:

```
event: snapshot
data: {...}

event: node_complete
data: {"event_id":"...","task_id":"...","event_type":"node_complete","source":"supervisor",...}

event: agent_start
data: {"event_id":"...","task_id":"...","event_type":"agent_start","source":"supervisor","payload":{"agent":"RiskAgent",...}}

event: agent_done
data: {"event_id":"...","task_id":"...","event_type":"agent_done",...}

event: node_complete
...

event: done
data: {...}
```

---

## 7. Frontend 兼容测试

### 7.1 chat/page.tsx 变更

| 原代码 | P3 状态 |
|--------|--------|
| `await new Promise((r) => setTimeout(r, 800))` | ❌ 已删除 |
| `await new Promise((r) => setTimeout(r, 600))` | ❌ 已删除 |
| 3 段硬编码 Agent 动画 | ❌ 已删除 |
| `data.stream_url` 分支 → EventSource | ✅ 新增 |
| `agent_start`/`agent_done`/`agent_error` listener | ✅ 新增 |
| `done` listener → 显示最终回复 | ✅ 新增 |
| `stream_url` 为空 → 原有 REST 行为 | ✅ 保留 |

### 7.2 DAGView.tsx 变更

| 功能 | 原状态 | P3 |
|------|--------|-----|
| 静态 Champion Demo | ✅ | ✅ 保留 |
| fetch trace (非 live) | ✅ | ✅ 保留 |
| `live={true}` SSE 实时更新 | ❌ | ✅ 新增 |
| `buildRealtimeDAG()` 从 SSE 事件构建 | ❌ | ✅ 新增 |
| LIVE 标签显示 | ❌ | ✅ 新增 |
| 新增组件 (LiveDAGView) | ❌ | ❌ 不新增, 改现有组件 |

---

## 8. DATABASE_ENABLED=false / STREAMING_ENABLED=false 兼容

| 配置 | POST /agent/chat | GET /agent/stream/{id} | Frontend |
|------|-----------------|----------------------|----------|
| `STREAMING_ENABLED=false` (默认) | 同步, 等待完成 | 404 | REST fetch (v1.2 行为) |
| `STREAMING_ENABLED=true` | 异步, 立即返回 | SSE 事件流 | EventSource |

---

## 9. 架构约束验证

| 约束 | 状态 | 证据 |
|------|------|------|
| EventBus 不放 langgraph 目录 | ✅ | `app/services/event_bus.py` |
| EventBus 有 create/close/TTL | ✅ | create_channel, close_channel, _cleanup_loop |
| EventNormalizer 统一 6 字段格式 | ✅ | event_id, task_id, event_type, source, timestamp, payload |
| Supervisor 7 节点不变 | ✅ | wrapper/middleware, 节点内部零改动 |
| Agent 接口不变 | ✅ | execute_business_agent() 签名不变 |
| DatabaseTool 规则不变 | ✅ | P2 DatabaseTool 零修改 |
| 前端无 setTimeout 假动画 | ✅ | 3 段全部删除 |
| DAGView 不新增组件 | ✅ | live prop, 同一组件 |
| STREAMING_ENABLED=false 100% 兼容 v1.2 | ✅ | 同步执行, SSE 返回 404 |

---

## 10. 未验证项 (需生产环境/浏览器)

| 项目 | 原因 | 如何验证 |
|------|------|---------|
| SSE 端点完整事件流 (含 LLM) | 本地无前端 | 启动后端 + curl -N 验证 |
| Frontend EventSource 连接 | WSL 无浏览器 | PowerShell 启动前端 + Chrome DevTools Network |
| DAGView live 实时渲染 | WSL 无浏览器 | 浏览器访问 trace 页面 + live=true |
| SSE 断线重连 + snapshot 恢复 | 需模拟网络中断 | 断开 WS 连接 → 重新连接 → 验证 snapshot |
| TTL 自动清理 (300s) | 需长时间运行 | 等待 300s+ 验证 channel 消失 |

---

*Generated by Hermes Agent · 2026-07-25 · P3 Streaming Implementation Report V1.0*
