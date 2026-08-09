# Industrial Park Agent Frontend Architecture V1.0

> 版本：V1.0 | 状态：READY FOR IMPLEMENTATION
> 技术栈：Next.js 15 + React 19 + TypeScript + Ant Design + Tailwind + ECharts + React Flow + Zustand
> 依赖：Unified API Contract V1.0, FastAPI Backend

---

## 1. 项目结构

```
industrial-agent-web/
  |
  ├── src/
  │   ├── app/                          # Next.js App Router
  │   │   ├── layout.tsx                # 根布局 (Ant Design ConfigProvider)
  │   │   ├── page.tsx                  # 首页 → redirect /dashboard
  │   │   │
  │   │   ├── agent/
  │   │   │   ├── chat/
  │   │   │   │   └── page.tsx          # AI 运营中心（核心页面）
  │   │   │   └── trace/
  │   │   │       └── [taskId]/
  │   │   │           └── page.tsx      # Agent Trace 可视化
  │   │   │
  │   │   ├── dashboard/
  │   │   │   ├── page.tsx              # 总览 Dashboard
  │   │   │   ├── investment/
  │   │   │   │   └── page.tsx          # 招商驾驶舱
  │   │   │   ├── industry/
  │   │   │   │   └── page.tsx          # 产业分析驾驶舱
  │   │   │   ├── risk/
  │   │   │   │   └── page.tsx          # 风险驾驶舱
  │   │   │   └── ai-ops/
  │   │   │       └── page.tsx          # AI运营中心
  │   │   │
  │   │   ├── enterprise/
  │   │   │   └── [id]/
  │   │   │       └── page.tsx          # 企业 360 画像
  │   │   │
  │   │   └── auth/
  │   │       └── login/
  │   │           └── page.tsx          # 登录页
  │   │
  │   ├── components/
  │   │   ├── layout/
  │   │   │   ├── AppLayout.tsx         # 整体布局（Sider + Header + Content）
  │   │   │   ├── Sidebar.tsx           # 侧边栏导航
  │   │   │   └── Header.tsx            # 顶部栏
  │   │   │
  │   │   ├── ai-chat/
  │   │   │   ├── ChatWindow.tsx        # 聊天窗口（核心组件）
  │   │   │   ├── MessageBubble.tsx     # 消息气泡
  │   │   │   ├── AgentThinking.tsx     # Agent 思考动画
  │   │   │   ├── ToolCallCard.tsx      # Tool 调用展示
  │   │   │   ├── StreamingText.tsx     # 流式文本渲染
  │   │   │   └── AgentProgress.tsx     # Agent 执行进度条
  │   │   │
  │   │   ├── agent-trace/
  │   │   │   ├── AgentGraph.tsx        # React Flow 执行图
  │   │   │   ├── TraceNode.tsx         # 自定义 Node
  │   │   │   ├── TraceEdge.tsx         # 自定义 Edge
  │   │   │   └── TraceTimeline.tsx     # 时间线视图
  │   │   │
  │   │   ├── dashboard/
  │   │   │   ├── KPICard.tsx           # KPI 数字卡片
  │   │   │   ├── ChartCard.tsx         # 图表卡片容器
  │   │   │   ├── InsightCard.tsx       # AI 洞察卡片
  │   │   │   └── MapPanel.tsx          # GIS 地图面板
  │   │   │
  │   │   ├── charts/
  │   │   │   ├── LineChart.tsx
  │   │   │   ├── PieChart.tsx
  │   │   │   ├── BarChart.tsx
  │   │   │   ├── FunnelChart.tsx
  │   │   │   ├── RadarChart.tsx
  │   │   │   └── GeoMap.tsx
  │   │   │
  │   │   └── enterprise/
  │   │       ├── EnterpriseProfile.tsx # 企业画像卡片
  │   │       ├── ScoreGauge.tsx        # 评分仪表盘
  │   │       └── RiskBadge.tsx         # 风险等级标签
  │   │
  │   ├── api/                          # API Client 封装
  │   │   ├── client.ts                 # Axios 实例 + JWT 拦截器
  │   │   ├── agent.api.ts              # Agent Chat/Task/Trace
  │   │   ├── investment.api.ts
  │   │   ├── policy.api.ts
  │   │   ├── risk.api.ts
  │   │   ├── industry.api.ts
  │   │   ├── service.api.ts
  │   │   ├── dashboard.api.ts
  │   │   └── auth.api.ts
  │   │
  │   ├── hooks/
  │   │   ├── useAgentChat.ts           # Agent 对话 Hook
  │   │   ├── useAgentTask.ts           # WebSocket 实时事件
  │   │   ├── useAgentTrace.ts          # Trace 数据获取
  │   │   ├── useDashboard.ts           # Dashboard 数据
  │   │   └── useAuth.ts                # 认证 Hook
  │   │
  │   ├── store/                        # Zustand 状态管理
  │   │   ├── chatStore.ts              # 聊天状态
  │   │   ├── agentStore.ts             # Agent 执行状态
  │   │   ├── dashboardStore.ts         # Dashboard 数据
  │   │   └── authStore.ts              # 认证状态
  │   │
  │   ├── types/
  │   │   ├── agent.ts                  # Agent 类型定义
  │   │   ├── enterprise.ts
  │   │   ├── dashboard.ts
  │   │   └── api.ts                    # API 响应类型
  │   │
  │   └── utils/
  │       ├── format.ts                 # 数据格式化
  │       └── constants.ts
  │
  ├── public/
  ├── tailwind.config.ts
  ├── next.config.js
  ├── Dockerfile
  └── package.json
```

---

## 2. 页面路由设计

```
/                         → Redirect to /dashboard
/login                    → 登录页

/dashboard                → AI园区运营总览（5 个 KPI 卡片 + 图表）
/dashboard/investment     → 招商驾驶舱（漏斗 + 企业排行）
/dashboard/industry       → 产业分析驾驶舱（知识图谱 + 趋势）
/dashboard/risk           → 风险驾驶舱（风险分布 + 预警）
/dashboard/ai-ops         → AI运营中心（Agent 调用统计）

/agent/chat               → AI 运营中心（与 Supervisor 对话）
/agent/trace/[taskId]     → Agent Trace 可视化

/enterprise/[id]          → 企业 360 画像
```

---

## 3. 核心组件设计

### 3.1 AI Chat 页面（核心体验）

```tsx
// app/agent/chat/page.tsx
export default function AgentChatPage() {
  const { messages, sendMessage, isStreaming, currentAgents } = useAgentChat();
  const { wsEvents, connect } = useAgentTask();
  
  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* 左侧：对话区 */}
      <div className="flex-1 flex flex-col">
        <ChatWindow messages={messages} isStreaming={isStreaming} />
        <ChatInput onSend={sendMessage} disabled={isStreaming} />
      </div>
      
      {/* 右侧：Agent 执行面板 */}
      <div className="w-96 border-l p-4">
        <AgentProgress agents={currentAgents} />
        <ToolCallLog events={wsEvents} />
      </div>
    </div>
  );
}
```

### 3.2 ChatWindow 消息类型

```typescript
type MessageType = 
  | "user_message"        // 用户输入
  | "supervisor_response" // Supervisor 回复
  | "agent_thinking"      // Agent 思考中
  | "agent_result"        // Agent 结果
  | "tool_call"           // 工具调用
  | "report"              // 最终报告（Markdown）
  | "error";              // 错误消息
```

### 3.3 StreamingText 组件

```tsx
// 流式渲染 LLM 输出（逐字显示）
export function StreamingText({ text, onComplete }: Props) {
  const [displayed, setDisplayed] = useState("");
  
  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        clearInterval(interval);
        onComplete?.();
      }
    }, 30);  // 30ms/字 ≈ 自然阅读速度
    
    return () => clearInterval(interval);
  }, [text]);
  
  return <Markdown>{displayed}</Markdown>;
}
```

### 3.4 Agent Trace 可视化

```tsx
// React Flow 渲染 Agent 执行链路
export function AgentGraph({ trace }: { trace: TraceData }) {
  const nodes = trace.steps.map((step, i) => ({
    id: `step-${i}`,
    type: step.type,  // supervisor / agent / tool
    position: { x: 100, y: i * 120 },
    data: {
      label: step.agent,
      action: step.action,
      duration: step.duration_ms,
      status: step.status
    }
  }));
  
  const edges = nodes.slice(1).map((node, i) => ({
    id: `edge-${i}`,
    source: `step-${i}`,
    target: `step-${i+1}`,
    animated: true
  }));
  
  return (
    <ReactFlow nodes={nodes} edges={edges} fitView>
      <Background />
      <Controls />
    </ReactFlow>
  );
}
```

---

## 4. WebSocket 集成

```typescript
// hooks/useAgentTask.ts
export function useAgentTask(taskId?: string) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket>();
  
  useEffect(() => {
    if (!taskId) return;
    
    const token = getAuthToken();
    const ws = new WebSocket(
      `${WS_URL}/api/v1/ws/task/${taskId}?token=${token}`
    );
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents(prev => [...prev, data]);
      
      // 根据事件类型更新 UI
      switch (data.type) {
        case "agent_started":
          // 显示 Agent 执行状态
          break;
        case "agent_completed":
          // 显示 Agent 结果
          break;
        case "streaming_text":
          // 追加流式文本
          break;
        case "task_completed":
          ws.close();
          break;
      }
    };
    
    wsRef.current = ws;
    return () => ws.close();
  }, [taskId]);
  
  return { events, connected };
}
```

---

## 5. 状态管理（Zustand）

```typescript
// store/chatStore.ts
interface ChatStore {
  messages: Message[];
  isStreaming: boolean;
  currentAgents: AgentStatus[];
  
  sendMessage: (text: string) => Promise<void>;
  addMessage: (msg: Message) => void;
  updateAgentStatus: (agent: string, status: string) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentAgents: [],
  
  sendMessage: async (text: string) => {
    set({ isStreaming: true });
    
    // 添加用户消息
    get().addMessage({ role: "user", content: text });
    
    // 调用 API
    const res = await agentApi.chat({ message: text, stream: true });
    const taskId = res.task_id;
    
    // 连接 WebSocket 获取实时事件
    connectWebSocket(taskId);
  },
  
  addMessage: (msg) => set(state => ({
    messages: [...state.messages, msg]
  })),
  
  updateAgentStatus: (agent, status) => set(state => ({
    currentAgents: state.currentAgents.map(a =>
      a.name === agent ? { ...a, status } : a
    )
  }))
}));
```

---

## 6. Dashboard 数据流

```typescript
// hooks/useDashboard.ts
export function useDashboard(type: DashboardType) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true);
      const res = await dashboardApi.getDashboard(type);
      setData(res.data);
      setLoading(false);
    };
    
    fetchDashboard();
    // 30 秒自动刷新
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, [type]);
  
  return { data, loading };
}
```

---

## 7. 关键依赖

```json
{
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "typescript": "5.6.0",
    "antd": "5.21.0",
    "@ant-design/icons": "5.5.0",
    "tailwindcss": "3.4.0",
    "echarts": "5.5.0",
    "echarts-for-react": "3.0.0",
    "reactflow": "11.11.0",
    "zustand": "5.0.0",
    "@tanstack/react-query": "5.60.0",
    "axios": "1.7.0",
    "react-markdown": "9.0.0",
    "dayjs": "1.11.0"
  }
}
```

---

## 8. 组件树全景

```
AppLayout
  ├── Sidebar
  │   ├── 园区总览
  │   ├── AI运营中心
  │   ├── 招商驾驶舱
  │   ├── 产业分析
  │   ├── 风险预警
  │   ├── AI运营驾驶舱
  │   └── Agent Trace
  │
  ├── Header
  │   ├── 园区选择器
  │   └── 用户头像
  │
  └── Content (路由)
      │
      ├── /dashboard
      │   ├── KPICard × 4 (企业总数/招商机会/风险/AI任务)
      │   ├── LineChart (企业增长趋势)
      │   ├── PieChart (产业分布)
      │   ├── GeoMap (企业GIS)
      │   └── InsightCard (AI洞察)
      │
      ├── /agent/chat
      │   ├── ChatWindow
      │   │   ├── MessageBubble (user)
      │   │   ├── AgentThinking
      │   │   ├── ToolCallCard
      │   │   └── MessageBubble (report, Markdown)
      │   ├── ChatInput
      │   └── AgentProgress Sidebar
      │       ├── AgentStatus × N
      │       └── ToolCallLog
      │
      └── /agent/trace/[taskId]
          └── AgentGraph (React Flow)
```

---

## 9. Docker 部署

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./
RUN npm ci --production
EXPOSE 3000
CMD ["npm", "start"]
```

```nginx
# nginx.conf 反向代理
server {
    listen 80;
    server_name industrial-park.local;
    
    location / {
        proxy_pass http://frontend:3000;
    }
    
    location /api/ {
        proxy_pass http://api:8000;
    }
    
    location /ws/ {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

**文档状态：READY FOR IMPLEMENTATION**
