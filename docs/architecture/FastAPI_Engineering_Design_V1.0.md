# FastAPI Backend Engineering Design V1.0

> 版本：V1.0 | 状态：READY FOR IMPLEMENTATION
> 技术栈：Python 3.12 + FastAPI + SQLAlchemy Async + LangGraph + PostgreSQL + Redis
> 提供给：React Frontend Agent, 所有 Business Agent

---

## 1. 项目结构

```
industrial-park-agent-backend/
  |
  ├── app/
  │   ├── main.py                    # FastAPI 入口
  │   ├── config.py                  # 配置管理
  │   │
  │   ├── api/
  │   │   └── v1/
  │   │       ├── __init__.py
  │   │       ├── agent.py           # Agent Chat + Task
  │   │       ├── task.py            # Task 管理
  │   │       ├── trace.py           # Trace 查询
  │   │       ├── websocket.py       # WebSocket
  │   │       ├── auth.py            # JWT 认证
  │   │       ├── enterprise.py      # 企业 API
  │   │       ├── investment.py      # 招商 API
  │   │       ├── policy.py          # 政策 API
  │   │       ├── risk.py            # 风险 API
  │   │       ├── industry.py        # 产业 API
  │   │       ├── service.py         # 企业服务 API
  │   │       ├── dashboard.py       # BI Dashboard
  │   │       └── health.py          # 健康检查
  │   │
  │   ├── core/
  │   │   ├── security.py            # JWT + RBAC
  │   │   ├── middleware.py           # Logging/CORS/RateLimit
  │   │   ├── exception.py           # 全局异常处理
  │   │   └── logger.py
  │   │
  │   ├── database/
  │   │   ├── session.py             # AsyncSession
  │   │   ├── base.py                # Base Model
  │   │   └── models/                # SQLAlchemy Models
  │   │       ├── enterprise.py
  │   │       ├── agent.py
  │   │       └── ...
  │   │
  │   ├── schemas/                   # Pydantic Models
  │   │   ├── agent.py
  │   │   ├── investment.py
  │   │   └── ...
  │   │
  │   ├── services/                  # 业务逻辑层
  │   │   ├── agent_service.py
  │   │   ├── investment_service.py
  │   │   └── ...
  │   │
  │   ├── langgraph/                 # LangGraph 运行时
  │   │   ├── graph.py               # Supervisor Graph
  │   │   ├── state.py               # State Schema
  │   │   ├── nodes/                 # 各 Agent Node
  │   │   │   ├── supervisor_nodes.py
  │   │   │   ├── investment_nodes.py
  │   │   │   ├── risk_nodes.py
  │   │   │   ├── policy_nodes.py
  │   │   │   ├── industry_nodes.py
  │   │   │   ├── service_nodes.py
  │   │   │   └── bi_nodes.py
  │   │   └── router.py              # 条件路由
  │   │
  │   ├── agents/                    # Agent 注册与调用
  │   │   ├── registry.py
  │   │   └── adapter.py             # LangGraph Adapter
  │   │
  │   ├── tools/                     # Tool Gateway
  │   │   ├── gateway.py
  │   │   ├── data_tools.py
  │   │   ├── knowledge_tools.py
  │   │   ├── analysis_tools.py
  │   │   └── memory_tools.py
  │   │
  │   └── websocket/
  │       ├── manager.py             # Connection Manager
  │       └── events.py              # Event Types
  │
  ├── alembic/                       # 数据库迁移
  ├── tests/
  ├── Dockerfile
  ├── docker-compose.yml
  ├── requirements.txt
  └── .env
```

---

## 2. 核心入口 main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.middleware import LoggingMiddleware, RateLimitMiddleware
from app.core.exception import register_exception_handlers
from app.api.v1 import router as v1_router
from app.database.session import init_db
from app.agents.registry import init_agent_registry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await init_agent_registry()
    yield
    # Shutdown
    await close_db()

app = FastAPI(
    title="Industrial Park Agent API",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

# Routes
app.include_router(v1_router, prefix="/api/v1")

# Exception handlers
register_exception_handlers(app)
```

---

## 3. 核心中间件

```python
# JWT 认证
async def jwt_middleware(request: Request, call_next):
    if request.url.path in ["/api/v1/auth/login", "/api/v1/health"]:
        return await call_next(request)
    
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = decode_jwt(token)
    request.state.user_id = payload["sub"]
    request.state.user_role = payload["role"]
    
    return await call_next(request)

# RBAC
def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if permission not in ROLE_PERMISSIONS.get(request.state.user_role, []):
                raise HTTPException(403, "Permission denied")
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# 速率限制 (Redis)
async def rate_limit_middleware(request: Request, call_next):
    key = f"rate_limit:{request.state.user_id}:{request.url.path}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > 100:  # 100 req/min
        raise HTTPException(429, "Rate limit exceeded")
    return await call_next(request)
```

---

## 4. LangGraph Adapter（核心集成）

```python
# FastAPI ↔ LangGraph 适配器
class LangGraphAdapter:
    """将 LangGraph StateGraph 封装为 FastAPI 可调用的 Agent Runtime"""
    
    def __init__(self):
        self.graph = build_supervisor_graph()
        self.agent_graphs = {
            "InvestmentAgent": build_investment_graph(),
            "RiskAgent": build_risk_graph(),
            "PolicyAgent": build_policy_graph(),
            "IndustryAgent": build_industry_graph(),
            "EnterpriseServiceAgent": build_service_graph(),
            "BIAgent": build_bi_graph()
        }
    
    async def invoke_supervisor(self, user_input: Dict) -> Dict:
        """执行 Supervisor 工作流"""
        initial_state = {
            "user_id": user_input["user_id"],
            "conversation_id": user_input.get("conversation_id", str(uuid4())),
            "user_query": user_input["message"],
            "status": "idle",
            "trace_id": str(uuid4()),
            "trace_steps": [],
            "agent_results": {}
        }
        
        config = {"configurable": {"thread_id": initial_state["conversation_id"]}}
        result = await self.graph.ainvoke(initial_state, config)
        return result
    
    async def invoke_agent(self, agent_name: str, task: Dict) -> Dict:
        """执行单个业务 Agent"""
        graph = self.agent_graphs.get(agent_name)
        if not graph:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        result = await graph.ainvoke(task)
        return result
```

---

## 5. Agent Chat API（核心端点）

```python
# POST /api/v1/agent/chat
@router.post("/agent/chat")
async def agent_chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    用户对话入口：接受自然语言，返回 Agent 执行结果
    
    支持两种模式：
    1. 同步：等待全部 Agent 完成
    2. 流式：返回 task_id，通过 WebSocket 获取实时事件
    """
    # 创建任务
    task = await agent_service.create_task(
        user_id=current_user.id,
        message=request.message,
        context=request.context
    )
    
    if request.stream:
        # 流式模式：后台执行，WebSocket 推送
        background_tasks.add_task(
            langgraph_adapter.invoke_supervisor,
            {"user_id": current_user.id, "message": request.message}
        )
        return {"task_id": task.task_id, "status": "running"}
    
    # 同步模式
    result = await langgraph_adapter.invoke_supervisor({
        "user_id": current_user.id,
        "message": request.message
    })
    
    return {
        "task_id": result["task_id"],
        "status": "completed",
        "response": result["final_response"],
        "agents_used": list(result["agent_results"].keys()),
        "trace_id": result["trace_id"]
    }
```

---

## 6. WebSocket 事件系统

```python
class WebSocketManager:
    """管理 WebSocket 连接和事件推送"""
    
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}
        self.redis = redis_client
    
    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        if task_id not in self.connections:
            self.connections[task_id] = []
        self.connections[task_id].append(websocket)
    
    async def broadcast(self, task_id: str, event: Dict):
        """推送事件到所有订阅该 task 的客户端"""
        # 同时通过 Redis Pub/Sub 广播（多进程支持）
        await self.redis.publish(f"ws:task:{task_id}", json.dumps(event))
        
        for ws in self.connections.get(task_id, []):
            try:
                await ws.send_json(event)
            except:
                await self.disconnect(task_id, ws)
    
    async def send_agent_events(self, task_id: str, state: Dict):
        """发送 Agent 执行过程中的事件"""
        events = [
            {"type": "task_started", "task_id": task_id},
            {"type": "intent_recognized", "intent": state.get("intent")},
            {"type": "agent_started", "agent": state.get("current_agent")},
            {"type": "agent_completed", "agent": state.get("current_agent")},
            {"type": "task_completed", "response": state.get("final_response")}
        ]
        for event in events:
            await self.broadcast(task_id, event)


# WS /api/v1/ws/task/{task_id}
@router.websocket("/ws/task/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str):
    await ws_manager.connect(task_id, websocket)
    
    try:
        while True:
            # 保持连接，监听 Redis 事件
            data = await websocket.receive_text()
            # 客户端可发送控制命令
    except WebSocketDisconnect:
        await ws_manager.disconnect(task_id, websocket)
```

---

## 7. Docker 部署

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/industrial_park
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db
      - redis

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: industrial_park
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf

volumes:
  pgdata:
```

---

## 8. requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0
alembic==1.13.0
langgraph==0.2.0
langchain==0.3.0
langchain-openai==0.2.0
pgvector==0.3.0
redis==5.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
pydantic==2.9.0
pydantic-settings==2.5.0
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
```

---

## 9. 环境变量

```bash
# .env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/industrial_park
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-3-small
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
LOG_LEVEL=INFO
```

---

**文档状态：READY FOR IMPLEMENTATION**
