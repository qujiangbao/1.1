# Industrial Park Agent v1.2 — Project Handoff

> For: OpenAI Codex CLI  
> Date: 2026-07-25  
> Commit: `8d7316b` on `feature/production-upgrade-v1.2`

---

## Quick Start

```bash
# Clone and checkout
git clone git@github.com:qujiangbao/1.1.git
cd 1.1
git checkout feature/production-upgrade-v1.2

# Backend (WSL / Linux)
cd backend
source .venv/bin/activate  # or: .venv/bin/python3
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Backend deps (if needed)
uv pip install -r backend/requirements.txt --python backend/.venv/bin/python3

# Frontend (Windows PowerShell ONLY — WSL npm on /mnt/d is too slow)
cd D:\industrial-park-v1.1\frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## Architecture

```
User → Nginx :80 → Next.js :3000 (Ant Design) + FastAPI :8000
                        ↓
           LangGraph Supervisor (7 nodes, StateGraph)
          ↙    ↓    ↓    ↓    ↓    ↘
   Industry  Investment  Risk  Policy  Service  BI
          ↘    ↓    ↓    ↓    ↓    ↙
            ToolGateway (18 tools, PERMISSIONS matrix)
                  ↓
       PostgreSQL 16/pgvector + Redis 7
```

**Key constraint**: Frontend MUST run in Windows PowerShell. Backend MUST run in WSL/Linux. Cross-filesystem npm operations timeout or corrupt `.next/`.

---

## Current State: All P0-P8 Complete

| Phase | Feature | Status | Commit |
|-------|---------|--------|--------|
| P0 | Enterprise Data Tool | ✅ | `eb6e30c` |
| P1 | Policy RAG + pgvector | ✅ | `5c930d2` |
| P2 | LangGraph PostgreSQL Checkpointer | ✅ | `4daa205` |
| P3 | SSE Real-Time Streaming | ✅ | `4c43f9f` |
| P4 | RBAC (6 roles, JWT+bcrypt) | ✅ | `b41ae11` |
| P5 | Alembic Migrations | ✅ | `f948482` |
| P6 | Docker Production Deploy | ✅ | `b5948ff` |
| P7 | System Acceptance (144/144) | ✅ | `d93e5c0` |
| P8 | Launch & Competition Finalization | ✅ | `8d7316b` |

## Non-Negotiable Constraints

1. **NEVER modify `main` branch** — it's the frozen v1.1 Competition Gold release
2. **All work on feature branches** off `main`, merge via PR
3. **Supervisor 7 nodes NEVER change structure** — only add hooks/filters inside existing nodes
4. **Agent interface NEVER changes** — `execute_business_agent(agent_name, task, state)` signature is frozen
5. **Design before code** — every non-trivial change needs a design doc in `docs/engineering/`
6. **Feature branches** — branch from `main`, not from `feature/production-upgrade-v1.2`
7. **Database rules**: all new persistence maps to existing 17 tables. No duplicate tables. Use DatabaseTool (P2 pattern)
8. **.venv is a symlink** to `/mnt/d/广智能/backend/.venv`. Don't delete it.
9. **Use `uv pip install`** not `pip` — the venv has no pip module
10. **SSH port 22 blocked** in China — git uses port 443 via `ssh.github.com`

## Key Files

```
backend/
├── app/
│   ├── main.py                          # FastAPI entry, lifespan
│   ├── config.py                        # All settings (Pydantic BaseSettings)
│   ├── langgraph/
│   │   ├── graph.py                     # Supervisor StateGraph + checkpointer
│   │   ├── state.py                     # SupervisorState TypedDict
│   │   └── nodes/
│   │       ├── supervisor_nodes.py      # 7 nodes + P3 wrappers + P4 RBAC filter
│   │       ├── policy_nodes.py          # PolicyAgent graph (P1)
│   │       ├── investment_nodes.py      # InvestmentAgent
│   │       ├── industry_nodes.py        # IndustryAgent
│   │       ├── risk_nodes.py            # RiskAgent
│   │       ├── service_nodes.py         # EnterpriseServiceAgent
│   │       └── bi_nodes.py              # BIAgent
│   ├── agents/
│   │   ├── registry.py                  # AGENT_REGISTRY (6 agents)
│   │   └── executor.py                  # execute_business_agent()
│   ├── tools/
│   │   ├── gateway.py                   # ToolGateway (18 tools, PERMISSIONS)
│   │   ├── database_tool.py             # P2: persistence layer
│   │   ├── knowledge_tool.py            # P1: policy RAG
│   │   └── adapters/                    # P0: enterprise data adapters
│   ├── services/
│   │   ├── event_bus.py                 # P3: publish/subscribe
│   │   ├── event_normalizer.py          # P3: format unification
│   │   └── stream_executor.py           # P3: async graph execution
│   ├── core/
│   │   ├── security.py                  # P4: JWT + bcrypt + UserContext
│   │   └── permissions.py               # P4: RBAC middleware + ROLE_AGENT_WHITELIST
│   ├── database/
│   │   ├── session.py                   # Async engine + Alembic migrations
│   │   └── models/
│   │       ├── business.py              # enterprise, policy, industry, risk (7 tables)
│   │       ├── runtime.py               # agent_task, agent_memory, conversation (5 tables)
│   │       └── rbac.py                  # users, roles, permissions (5 tables) + seed data
│   └── api/v1/
│       ├── __init__.py                  # Router registry with RBAC guards
│       ├── agent.py                     # POST /agent/chat (dual-mode sync/async)
│       ├── auth.py                      # POST /auth/login, refresh, GET /auth/me
│       ├── stream.py                    # P3: GET /agent/stream/{id} SSE
│       ├── admin.py                     # P4: GET/POST /admin/users
│       ├── health.py                    # P6: health + DB check
│       ├── business.py                  # P0: enterprise + policy endpoints
│       ├── dashboard.py                 # Dashboard KPI/overview
│       ├── task.py                      # Task CRUD
│       └── trace.py                     # DAG trace
├── migrations/                          # P5: Alembic
│   ├── env.py                           # Async PostgreSQL engine
│   └── versions/v001_initial_schema.py  # 17-table initial schema
├── alembic.ini
├── Dockerfile
└── requirements.txt
```

## Git Workflow

```bash
# Remote
origin: git@github.com:qujiangbao/1.1.git

# Active branch
feature/production-upgrade-v1.2

# SSH config (~/.ssh/config)
Host github.com
    Hostname ssh.github.com
    Port 443
    User git

# Creating new feature (from main, not from upgrade branch)
git checkout main
git checkout -b feature/my-new-feature
# ... work ...
git push -u origin feature/my-new-feature
# Create PR to merge into main
```

## Environment Variables (.env)

```bash
APP_ENV=development
DATABASE_ENABLED=false        # true for production
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379
DEEPSEEK_API_KEY=***
STREAMING_ENABLED=false       # true for SSE real-time
STREAMING_HEARTBEAT_SECONDS=15
AUTH_ENABLED=false            # true for RBAC login
JWT_SECRET=change-this
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
ENTERPRISE_DATA_SOURCE=mock   # mock | tianyancha | qichacha | government
POLICY_RAG_MODE=mock          # mock | production
CORS_ORIGINS=http://localhost:3000
```

## Common Pitfalls

1. **WSL npm**: Always fails on /mnt/d. Use PowerShell for frontend.
2. **pip missing**: The .venv has no pip module. Use `uv pip install <pkg> --python .venv/bin/python3`
3. **curl + proxy**: WSL HTTP_PROXY interferes. Use `--noproxy '*'` when curling localhost
4. **Import hangs**: `app.database.models.runtime` can hang 30s on first load. Retry.
5. **Alembic init timed out**: The `alembic init` command hangs in WSL. Structure was created manually.
6. **.venv symlink**: v1.1's .venv points to v1.0's venv at `/mnt/d/广智能/backend/.venv`
7. **Design first**: Jumping to code without a design doc will be rejected. Always write `docs/engineering/<Name>_V<version>.md` first.
8. **Verification**: Long scripts in heredoc timeout (>120s). Write to `/tmp/hermes-verify-<phase>.py` first, then run.
9. **main branch frozen**: Never commit to main. It contains v1.1 Competition Gold release.

## Running Tests

```bash
# Backend syntax + unit (fast, no LLM)
cd backend
PYTHONPATH=. timeout 90 .venv/bin/python3 /tmp/hermes-verify-p7.py

# Full acceptance (144 checks)
cd backend
PYTHONPATH=. timeout 120 .venv/bin/python3 /tmp/hermes-acceptance-p7.py

# E2E (requires running server)
./e2e-test.sh http://localhost:8000

# Docker
./deploy.sh build   # first time
./deploy.sh health  # verify
```

## Next Steps (Post-P8)

- Connect real data sources (production `.env` with API keys)
- HTTPS via Let's Encrypt
- Rate limiting middleware
- Redis caching layer
- Deploy to RainYun server (`191.40.37.253`, path `/www/wwwroot/industrial-park/`)
- Run competition demo using `warmup.sh` → `e2e-test.sh` → 5-minute script
