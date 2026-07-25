# P4 RBAC Architecture V1.0

> **P4 基于角色的访问控制**  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-25  
> **前置**: P0 Enterprise ✅ | P1 Policy RAG ✅ | P2 Checkpointer ✅ | P3 Streaming ✅

---

## 1. 当前 Auth 系统审计

### 1.1 现状

```
POST /auth/login { username, password }
  → authenticate_admin()  ← hardcoded admin/password 对比
  → create_access_token({ sub: "admin", role: "park_manager" })  ← role 硬编码
  → { access_token, token_type: "bearer" }

所有 API 路由:
  → Depends(require_user)  ← 仅验证 JWT validity
  → 无角色检查 (任何人都能访问任何端点)
```

### 1.2 问题清单

| # | 问题 | 严重度 |
|---|------|--------|
| 1 | 单一硬编码用户 (admin)，无多用户系统 | 🔴 高 |
| 2 | Role 硬编码为 `park_manager`，全局统一 | 🔴 高 |
| 3 | 无 Access/Refresh Token 机制 | 🟡 中 |
| 4 | ToolGateway 有 Agent-Tool 权限矩阵，但无用户级 RBAC | 🟡 中 |
| 5 | API 端点无角色区分 (所有人都能访问所有功能) | 🔴 高 |
| 6 | 前端无权限菜单隐藏 | 🟡 中 |

---

## 2. RBAC 模型设计

### 2.1 角色定义

| 角色 | 标识 | 说明 |
|------|------|------|
| `SUPER_ADMIN` | super_admin | 超级管理员，所有权限 |
| `PARK_MANAGER` | park_manager | 产业园经理，全功能（默认 v1.1 等价） |
| `INVESTMENT_MANAGER` | investment_manager | 招商经理，招商+企业+产业分析 |
| `POLICY_MANAGER` | policy_manager | 政策经理，政策+企业查询 |
| `ENTERPRISE_SERVICE` | enterprise_service | 企业服务，工单+企业查询 |
| `VIEWER` | viewer | 只读，Dashboard + 查看 |

### 2.2 角色-Agent 权限映射

| Agent / 功能 | SUPER_ADMIN | PARK_MANAGER | INVESTMENT_MANAGER | POLICY_MANAGER | ENTERPRISE_SERVICE | VIEWER |
|-------------|:--:|:--:|:--:|:--:|:--:|:--:|
| Supervisor (编排) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| InvestmentAgent | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| PolicyAgent | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| IndustryAgent | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| RiskAgent | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| EnterpriseServiceAgent | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| BIAgent (Dashboard) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| User Management | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| System Config | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

### 2.3 角色-API 端点映射

| API 端点 | SUPER_ADMIN | PARK_MANAGER | INVESTMENT_MANAGER | POLICY_MANAGER | ENTERPRISE_SERVICE | VIEWER |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|
| POST /agent/chat | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GET /agent/checkpoint/{id} | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| GET /agent/task/{id}/trace | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| GET /agent/stream/{id} | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| POST /investment/search | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET /investment/{id} | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST /policy/search | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| POST /risk/scan | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET /dashboard/* | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GET /admin/users | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| POST /admin/users | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 3. JWT 认证升级

### 3.1 Token 机制

```
POST /auth/login { username, password }
  → 验证用户凭据 (从 users 表查询 + hash 对比)
  → 生成 Access Token (短期, 24h)
  → 生成 Refresh Token (长期, 30d)
  → 返回 { access_token, refresh_token, user: { id, username, role } }

POST /auth/refresh { refresh_token }
  → 验证 refresh_token
  → 生成新的 access_token
  → 返回 { access_token }
```

### 3.2 Token Payload

```python
# Access Token payload
{
    "sub": "user-001",           # user UUID
    "username": "zhangsan",      # 用户名
    "role": "investment_manager", # RBAC 角色
    "park_id": "park-gz",        # 所属园区
    "iat": 1750000000,
    "exp": 1750086400,           # 24h
    "type": "access"
}

# Refresh Token payload
{
    "sub": "user-001",
    "iat": 1750000000,
    "exp": 1752678400,           # 30d
    "type": "refresh"
}
```

### 3.3 User Context

```python
# app/core/security.py — P4 升级

class UserContext:
    """从 JWT 解析的用户上下文，注入到 request.state"""
    user_id: str
    username: str
    role: str           # one of ROLES
    park_id: str | None

# require_user → 解析 JWT → 返回 UserContext
async def require_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserContext:
    if not settings.auth_enabled:
        return UserContext(user_id="demo-user", username="demo", role="park_manager")
    payload = verify_token(token)
    return UserContext(
        user_id=payload["sub"],
        username=payload["username"],
        role=payload["role"],
        park_id=payload.get("park_id"),
    )

# require_role(min_role) → 检查用户角色是否满足最低要求
def require_role(*allowed_roles: str):
    def checker(user: UserContext = Depends(require_user)):
        if user.role not in allowed_roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker
```

---

## 4. Supervisor 集成

### 4.1 User Context 注入

```
POST /agent/chat
  │
  ├─ require_user → UserContext { user_id, username, role, park_id }
  │
  ├─ state["user_role"] = user_context.role    ← 已有字段，升级为实际角色
  ├─ state["user_id"] = user_context.user_id   ← 升级为实际用户 ID
  │
  ├─ graph.ainvoke(state, config)
  │     │
  │     ├─ task_planner_node: 根据 user_context.role 过滤可调用的 Agent
  │     │     intents → 仅保留用户角色允许的 Agent
  │     │
  │     └─ agent_router_node: 不变 (task_plan 已过滤)
  │
  └─ 返回结果
```

### 4.2 Task Planner 角色感知改造

```python
# supervisor_nodes.py — task_planner_node P4 增强

# 角色 → 允许的 Agent 列表
ROLE_AGENT_WHITELIST = {
    "super_admin":          ["*"],
    "park_manager":         ["*"],
    "investment_manager":   ["InvestmentAgent", "IndustryAgent", "RiskAgent"],
    "policy_manager":       ["PolicyAgent"],
    "enterprise_service":   ["EnterpriseServiceAgent"],
    "viewer":               [],  # 只能看 Dashboard
}

def task_planner_node(state: SupervisorState) -> SupervisorState:
    intents = state.get("intents", [])
    user_role = state.get("user_role", "park_manager")
    allowed = ROLE_AGENT_WHITELIST.get(user_role, ["*"])
    
    task_plan = []
    for intent in intents:
        agent = INTENT_ROUTING.get(intent)
        if not agent:
            continue
        # P4: 角色过滤 — 跳过无权限的 Agent
        if "*" not in allowed and agent not in allowed:
            continue
        task_plan.append({...})
    
    state["task_plan"] = task_plan
    return state
```

### 4.3 约束遵守

| 约束 | 状态 |
|------|------|
| Supervisor 7 节点不变 | ✅ 仅 task_planner_node 增加角色过滤逻辑 |
| Agent 接口不变 | ✅ execute_business_agent() 签名不变 |
| ToolGateway 规则不变 | ✅ 权限检查逻辑保留，用户级 RBAC 在 API 层 |

---

## 5. 数据库设计

### 5.1 新增表 (遵循 Database Architecture V1.0 映射规则)

```
users
  ├─ user_id (PK)
  ├─ username (unique)
  ├─ password_hash
  ├─ display_name
  ├─ park_id
  ├─ is_active
  ├─ created_at
  └─ updated_at

roles
  ├─ role_id (PK)
  ├─ name (unique)         → super_admin, park_manager, ...
  ├─ display_name
  └─ description

permissions
  ├─ permission_id (PK)
  ├─ code (unique)          → agent:investment, api:dashboard, tool:risk_scoring
  ├─ resource_type          → agent / api / tool / dashboard
  ├─ resource_name
  └─ action                 → read / write / execute

user_roles
  ├─ user_id (FK → users)
  └─ role_id (FK → roles)
  (composite PK)

role_permissions
  ├─ role_id (FK → roles)
  └─ permission_id (FK → permissions)
  (composite PK)
```

### 5.2 SQLAlchemy Models (app/database/models/rbac.py)

```python
class User(Base):
    __tablename__ = "users"
    user_id = Column(String(50), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(200))
    park_id = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Role(Base):
    __tablename__ = "roles"
    role_id = Column(String(50), primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100))
    description = Column(Text)

class Permission(Base):
    __tablename__ = "permissions"
    permission_id = Column(String(50), primary_key=True)
    code = Column(String(100), unique=True, nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_name = Column(String(200))
    action = Column(String(50), default="execute")

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id = Column(String(50), ForeignKey("users.user_id"), primary_key=True)
    role_id = Column(String(50), ForeignKey("roles.role_id"), primary_key=True)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column(String(50), ForeignKey("roles.role_id"), primary_key=True)
    permission_id = Column(String(50), ForeignKey("permissions.permission_id"), primary_key=True)
```

### 5.3 种子数据

```python
# 预置 6 个角色
ROLE_SEEDS = [
    ("role-super-admin",      "super_admin",          "超级管理员"),
    ("role-park-manager",     "park_manager",         "产业园经理"),
    ("role-investment-mgr",   "investment_manager",   "招商经理"),
    ("role-policy-mgr",       "policy_manager",       "政策经理"),
    ("role-service",          "enterprise_service",   "企业服务"),
    ("role-viewer",           "viewer",               "只读用户"),
]

# 预置权限
PERMISSION_SEEDS = [
    # Agent 执行权限
    ("perm-agent-investment", "agent:investment", "agent", "InvestmentAgent", "execute"),
    ("perm-agent-policy",     "agent:policy",     "agent", "PolicyAgent", "execute"),
    ("perm-agent-industry",   "agent:industry",   "agent", "IndustryAgent", "execute"),
    ("perm-agent-risk",       "agent:risk",       "agent", "RiskAgent", "execute"),
    ("perm-agent-service",    "agent:service",    "agent", "EnterpriseServiceAgent", "execute"),
    ("perm-agent-bi",         "agent:bi",         "agent", "BIAgent", "execute"),
    # API 访问权限
    ("perm-api-chat",         "api:chat",         "api", "/agent/chat", "read"),
    ("perm-api-trace",        "api:trace",        "api", "/agent/task/*/trace", "read"),
    ("perm-api-stream",       "api:stream",       "api", "/agent/stream/*", "read"),
    ("perm-api-investment",   "api:investment",   "api", "/investment/*", "read"),
    ("perm-api-policy",       "api:policy",       "api", "/policy/*", "read"),
    ("perm-api-risk",         "api:risk",         "api", "/risk/*", "read"),
    ("perm-api-dashboard",    "api:dashboard",    "api", "/dashboard/*", "read"),
    ("perm-api-admin",        "api:admin",        "api", "/admin/*", "write"),
]

# 预置 admin 用户 (密码: admin123 → bcrypt hash)
DEFAULT_ADMIN = User(
    user_id="user-admin-001",
    username="admin",
    password_hash=hash_password("admin123"),
    display_name="系统管理员",
    is_active=True,
)
```

---

## 6. Permission 中间件

### 6.1 API 层权限检查

```python
# app/core/permissions.py (新建)

from fastapi import Depends, HTTPException
from app.core.security import UserContext, require_user

# 角色层级 (数字越大权限越高)
ROLE_HIERARCHY = {
    "viewer": 0,
    "enterprise_service": 1,
    "policy_manager": 2,
    "investment_manager": 3,
    "park_manager": 4,
    "super_admin": 5,
}

def require_min_role(min_role: str):
    """要求用户角色 >= min_role"""
    async def checker(user: UserContext = Depends(require_user)):
        user_level = ROLE_HIERARCHY.get(user.role, -1)
        required_level = ROLE_HIERARCHY.get(min_role, 999)
        if user_level < required_level:
            raise HTTPException(403, f"Requires {min_role} or higher")
        return user
    return checker

def require_any_role(*roles: str):
    """要求用户拥有任一角色"""
    async def checker(user: UserContext = Depends(require_user)):
        if user.role not in roles:
            raise HTTPException(403, f"Requires one of: {', '.join(roles)}")
        return user
    return checker
```

### 6.2 API 路由保护示例

```python
# app/api/v1/__init__.py — P4 升级

from app.core.permissions import require_min_role, require_any_role

# Agent chat: 所有角色可用
router.include_router(agent.router, tags=["Agent"],
    dependencies=[Depends(require_user)])

# Dashboard: viewer+ 可用
router.include_router(dashboard.router, tags=["Dashboard"],
    dependencies=[Depends(require_min_role("viewer"))])

# Admin: super_admin only
router.include_router(admin.router, tags=["Admin"],
    dependencies=[Depends(require_any_role("super_admin"))])
```

---

## 7. Frontend 权限集成

### 7.1 登录页升级

```typescript
// P4: 登录后存储 user info 到 context/state
POST /auth/login
  → { access_token, refresh_token, user: { id, username, role, display_name } }
  → localStorage.setItem("token", access_token)
  → localStorage.setItem("refresh_token", refresh_token)
  → useContext(UserContext).setUser(user)
```

### 7.2 权限菜单隐藏

```typescript
// 方式: useUserRole() hook → 条件渲染

const { role } = useUserContext();

// 侧边栏菜单过滤
const menuItems = [
  { key: "agent-chat", label: "AI 对话", show: true },              // 所有角色
  { key: "investment", label: "招商管理", show: canAccess(role, ["super_admin", "park_manager", "investment_manager"]) },
  { key: "policy",     label: "政策中心", show: canAccess(role, ["super_admin", "park_manager", "policy_manager"]) },
  { key: "risk",       label: "风险管理", show: canAccess(role, ["super_admin", "park_manager", "investment_manager"]) },
  { key: "dashboard",  label: "数据驾驶舱", show: true },          // 所有角色
  { key: "admin",      label: "系统管理", show: canAccess(role, ["super_admin"]) },
];

// Agent 协作面板 → 按角色过滤可见 Agent
const visibleAgents = DEFAULT_AGENTS.filter(a => 
  role === "super_admin" || role === "park_manager" || agentRoleMap[a.name]?.includes(role)
);
```

### 7.3 Dashboard 数据权限

```typescript
// Dashboard 数据过滤: VIEWER 只能看汇总, PARK_MANAGER 看全部
async function fetchDashboardData(role: string) {
  const baseData = await apiFetch("/api/v1/dashboard/overview");
  if (role === "viewer") {
    return { ...baseData, sensitive_data: undefined }; // 隐藏敏感数据
  }
  return baseData;
}
```

---

## 8. 约束遵守

| 约束 | 状态 | 说明 |
|------|------|------|
| 不改变 Supervisor 7 节点架构 | ✅ | 仅 task_planner_node 增加角色过滤 (ROLE_AGENT_WHITELIST) |
| 不改变 Agent 接口 | ✅ | execute_business_agent() 签名不变 |
| 不改变 ToolGateway 规则 | ✅ | PERMISSIONS 矩阵保留，用户级 RBAC 在 API 层 |
| 兼容 Database Architecture V1.0 | ✅ | 5 新表映射到已有数据库，不重复 |
| AUTH_ENABLED=false 兼容 | ✅ | 回退到 demo-user + park_manager 硬编码 |
| Mock 模式兼容 | ✅ | DATABASE_ENABLED=false → 使用内存用户字典 |

---

## 9. 文件变更预估

| # | 文件 | 操作 | 行数 | 类别 |
|---|------|------|------|------|
| 1 | `backend/app/database/models/rbac.py` | **新建** | ~80 | RBAC 模型 |
| 2 | `backend/app/core/security.py` | 修改 | +60 | JWT 升级 + UserContext |
| 3 | `backend/app/core/permissions.py` | **新建** | ~40 | 权限中间件 |
| 4 | `backend/app/api/v1/auth.py` | 修改 | +80 | Login/Refresh/Me |
| 5 | `backend/app/api/v1/admin.py` | **新建** | ~100 | 用户管理 CRUD |
| 6 | `backend/app/api/v1/__init__.py` | 修改 | +10 | 角色路由保护 |
| 7 | `backend/app/langgraph/nodes/supervisor_nodes.py` | 修改 | +15 | 角色过滤 Agent |
| 8 | `backend/app/config.py` | 修改 | +3 | AUTH_ENABLED 保持不变 |
| 9 | `backend/app/database/models/__init__.py` | 修改 | +3 | RBAC 模型导出 |
| 10 | `frontend/src/contexts/UserContext.tsx` | **新建** | ~50 | 用户上下文 |
| 11 | `frontend/src/app/auth/login/page.tsx` | 修改 | +20 | 角色信息存储 |
| 12 | `frontend/src/components/layout/AppLayout.tsx` | 修改 | +30 | 权限菜单 |
| **合计** | **12 文件** | | **~500** | |

---

## 10. 验收清单

- [ ] `AUTH_ENABLED=false` → demo-user 行为与 v1.2 一致
- [ ] `POST /auth/login` 返回 `{ access_token, refresh_token, user }`
- [ ] `POST /auth/refresh` 刷新 access_token
- [ ] `GET /auth/me` 返回当前用户信息
- [ ] 5 个 RBAC 表通过 `init_db()` 自动创建
- [ ] 种子数据 (6 roles, 14 permissions, 1 admin user) 自动插入
- [ ] `require_min_role("park_manager")` 拒绝 viewer
- [ ] `task_planner_node` 按角色过滤 Agent (INVESTMENT_MANAGER 无法调用 PolicyAgent)
- [ ] Frontend 侧边栏按角色隐藏菜单项
- [ ] Admin API (`/admin/users`) 仅 super_admin 可访问
- [ ] P0/P1/P2/P3 所有现有测试通过

---

*Generated by Hermes Agent · 2026-07-25 · RBAC Architecture V1.0*
