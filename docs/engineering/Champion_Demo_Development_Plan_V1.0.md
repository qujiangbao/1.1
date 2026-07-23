# Champion Demo Development Plan V1.0

> 版本：V1.0 | 目标：将冠军 Demo 方案映射到现有代码

---

## 一、新增页面

### 1. Agent Team 页面

| 项目 | 内容 |
|------|------|
| 路由 | `/agent/team` |
| 文件 | `frontend/src/app/agent/team/page.tsx` |
| 依赖 API | `GET /api/v1/agent/status`（已有） |
| 功能 | 6 个 Agent 卡片 + 实时状态 + 执行时间线 |

### 2. AI 运营日报页面

| 项目 | 内容 |
|------|------|
| 路由 | `/dashboard` 增强 |
| 文件 | `frontend/src/app/dashboard/page.tsx`（修改） |
| 功能 | 顶部增加"今日 AI 运营日报"卡片 |

---

## 二、新增 API

### 1. Agent 团队实时状态

```
GET /api/v1/agent/team/status
→ 已有 GET /api/v1/agent/status，需增强返回格式
```

**需增强字段**：
```json
{
  "agents": {
    "InvestmentAgent": {
      "display": "AI招商经理",
      "capabilities": ["enterprise_search", ...],
      "last_task": "企业搜索与评分",        // ← 新增
      "last_execution_time_ms": 3200,      // ← 新增
      "tasks_completed_today": 45,          // ← 新增
      "status": "idle"                     // ← 新增
    }
  }
}
```

### 2. AI 运营日报

```
GET /api/v1/agent/daily-report
→ 新增
```

**返回**：
```json
{
  "date": "2026-07-21",
  "summary": "园区运营稳定，机器人产业热度上升",
  "park_metrics": {"total": 12580, "new": 45, "growth": "3.2%"},
  "investment": {"opportunities": 230, "signed": 12},
  "risk_alerts": [{"enterprise": "...", "level": "HIGH", "reason": "..."}],
  "policy_matches": 8,
  "ai_tasks_completed": 1520,
  "recommendations": ["加大机器人传感器方向招商力度"]
}
```

**实现位置**：`backend/app/api/v1/business.py`

---

## 三、新增数据库字段

无需新增字段。现有 `agent_task`、`agent_execution`、`agent_trace` 表已覆盖。

---

## 四、需要修改的前端组件

### 1. AI Chat 页面 — Agent 状态面板增强

**文件**：`frontend/src/app/agent/chat/page.tsx`

**改动**：
- 右侧 Agent 面板从简单列表改为**卡片式**
- 每个 Agent 卡片显示：头像图标、名称、状态动画、耗时
- 增加"全部 Agent"和"只看活跃"切换

### 2. Agent Trace 页面 — DAG 可视化

**文件**：`frontend/src/app/agent/trace/[taskId]/page.tsx`

**改动**：
- 从 Timeline 列表改为**DAG 流程图**
- 展示并行关系（RiskAgent 和 PolicyAgent 同时执行）
- 用不同颜色区分：蓝色=Supervisor、绿色=Agent、橙色=Tool

### 3. Dashboard — 增加 AI 日报

**文件**：`frontend/src/app/dashboard/page.tsx`

**改动**：
- 顶部增加日报卡片："今日 AI 运营日报"
- 调用 `GET /api/v1/agent/daily-report`

### 4. 新增 Agent Team 页面

**文件**：`frontend/src/app/agent/team/page.tsx`（新建）

**组件**：
- 6 个 AgentCard 组件
- AgentTimeline 时间线组件
- 使用 `GET /api/v1/agent/status`

### 5. 侧边栏导航更新

**文件**：`frontend/src/components/layout/AppLayout.tsx`

**改动**：增加"Agent 团队"菜单项

---

## 五、需要修改的后端

### 1. Agent Status API 增强

**文件**：`backend/app/api/v1/task.py`

**改动**：返回每个 Agent 的最后执行任务和耗时

### 2. 新增 Daily Report API

**文件**：`backend/app/api/v1/business.py`

**改动**：新增 `GET /api/v1/agent/daily-report` 路由

### 3. Supervisor 节点增强

**文件**：`backend/app/langgraph/nodes/supervisor_nodes.py`

**改动**：在 agent_router_node 中记录每个 Agent 的执行时间和任务描述到 `agent_task` 表

---

## 六、实施优先级

| 优先级 | 改动 | 文件 | 影响 |
|:---:|------|------|------|
| P0 | Agent 状态面板增强 | chat/page.tsx | 核心 Demo 展示 |
| P0 | 侧边栏加 Agent Team | AppLayout.tsx | 导航入口 |
| P0 | Daily Report API | business.py | 日报数据 |
| P1 | Agent Team 页面 | team/page.tsx | 多 Agent 证明 |
| P1 | Trace DAG 可视化 | trace/page.tsx | 可解释 AI |
| P1 | Agent Status API 增强 | task.py | 状态数据 |
| P2 | Dashboard 日报卡片 | dashboard/page.tsx | 锦上添花 |

---

## 七、预估工作量

| 改动 | 预计时间 |
|------|:---:|
| Agent 状态面板增强 | 30 分钟 |
| 侧边栏导航更新 | 5 分钟 |
| Daily Report API | 20 分钟 |
| Agent Team 页面 | 40 分钟 |
| Trace DAG 可视化 | 40 分钟 |
| Agent Status API 增强 | 15 分钟 |
| Dashboard 日报 | 20 分钟 |
| **总计** | **约 3 小时** |

---

**文档状态：READY TO IMPLEMENT**
