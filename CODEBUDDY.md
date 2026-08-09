# Industrial Park Agent — AI Development Context

> For: AI coding assistants (Claude Code, Codex, Hermes Agent)
> Version: V1.3 | Branch: `feature/production-upgrade-v1.2`

---

## Quick Start

```bash
# Backend (WSL/Linux)
cd /mnt/d/industrial-park-v1.1/backend
source .venv312/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Backend deps
uv pip install -r backend/requirements.txt --python .venv312/bin/python

# Frontend (Windows PowerShell ONLY)
cd D:\industrial-park-v1.1\frontend
npm install && npm run dev
```

## Architecture (FROZEN)

```
User → Nginx :80 → Next.js :3000 + FastAPI :8000
                ↓
       LangGraph Supervisor (7 nodes, StateGraph)
      ↙    ↓    ↓    ↓    ↓    ↘
Industry Investment Risk Policy Service  BI
      ↘    ↓    ↓    ↓    ↓    ↙
        ToolGateway (18 tools, PERMISSIONS)
              ↓
   PostgreSQL 16/pgvector + Redis 7
```

Architecture details: `docs/ARCHITECTURE.md` (Single Source of Truth)

## Hard Constraints

1. **NEVER modify `main` branch** — frozen V1.1 Competition Gold release
2. **Feature branches off `main`**, merge via PR
3. **Supervisor 7 nodes NEVER change structure** — only add hooks/filters inside existing nodes
4. **Agent interface NEVER changes** — `execute_business_agent(agent_name, task, state)` is frozen
5. **Design before code** — every non-trivial change needs a design doc in `docs/engineering/`
6. **Feature branches** — branch from `main`, not from `feature/production-upgrade-v1.2`
7. **Database rules**: 17 tables frozen. No duplicate tables. Use DatabaseTool pattern.
8. **Use `uv pip install`** not `pip` — the venv has no pip module
9. **Frontend MUST run in Windows PowerShell** — WSL npm on /mnt/d fails
10. **SSH port 22 blocked** in China — git uses port 443 via `ssh.github.com`
11. **No fabricated data** — `data_available=false` means stay in mock mode

## Key Source Files

```
backend/app/
├── main.py                          # FastAPI entry, lifespan
├── config.py                        # All settings
├── langgraph/
│   ├── graph.py                     # Supervisor StateGraph
│   ├── state.py                     # SupervisorState TypedDict
│   └── nodes/
│       ├── supervisor_nodes.py      # 7 nodes + RBAC filter
│       ├── policy_nodes.py          # PolicyAgent (P1)
│       ├── investment_nodes.py      # InvestmentAgent
│       ├── industry_nodes.py        # IndustryAgent
│       ├── risk_nodes.py            # RiskAgent
│       ├── service_nodes.py         # EnterpriseServiceAgent
│       └── bi_nodes.py              # BIAgent
├── agents/
│   ├── registry.py                  # AGENT_REGISTRY (6 agents)
│   └── executor.py                  # execute_business_agent()
├── tools/
│   ├── gateway.py                   # ToolGateway (18 tools, PERMISSIONS)
│   ├── database_tool.py             # Persistence layer
│   ├── knowledge_tool.py            # Policy RAG (P1)
│   └── adapters/                    # Enterprise data adapters (P0)
├── services/
│   ├── event_bus.py                 # Publish/subscribe (P3)
│   ├── event_normalizer.py          # Format unification (P3)
│   └── stream_executor.py           # Async graph execution (P3)
├── core/
│   ├── security.py                  # JWT + bcrypt (P4)
│   └── permissions.py               # RBAC middleware (P4)
├── database/
│   ├── session.py                   # Async engine + Alembic
│   └── models/
│       ├── business.py              # 7 tables
│       ├── runtime.py               # 5 tables
│       └── rbac.py                  # 5 tables + seed
└── api/v1/
    ├── agent.py                     # POST /agent/chat
    ├── auth.py                      # POST /auth/login
    ├── stream.py                    # SSE real-time (P3)
    ├── admin.py                     # User management (P4)
    └── ...
```

## Environment (.env)

```bash
APP_ENV=development
DATABASE_ENABLED=false              # true for production
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379
DEEPSEEK_API_KEY=***
STREAMING_ENABLED=false             # true for SSE
AUTH_ENABLED=false                  # true for RBAC
ENTERPRISE_DATA_SOURCE=mock         # mock | tianyancha | qichacha
POLICY_RAG_MODE=crawl4ai            # crawl4ai | pgvector | mock
CORS_ORIGINS=http://localhost:3000
```

## Git Workflow

```bash
origin: git@github.com:qujiangbao/1.1.git
active: feature/production-upgrade-v1.2

# SSH (~/.ssh/config)
Host github.com
    Hostname ssh.github.com
    Port 443

# New feature
git checkout main
git checkout -b feature/my-feature
git push -u origin feature/my-feature
# PR → merge into main
```

## Running Tests

```bash
# Backend (fast, no LLM)
cd backend && PYTHONPATH=. timeout 90 .venv312/bin/python -m pytest -q

# E2E
./e2e-test.sh http://localhost:8000

# Docker
./deploy.sh build && ./deploy.sh health
```

## Document Navigation

- Architecture (FROZEN): `docs/ARCHITECTURE.md`
- Agent index: `docs/agent-index.md`
- Document index: `docs/doc-index.md`
- Design specs: `docs/architecture/`
- Agent designs: `docs/agents/`
- Engineering docs: `docs/engineering/`
- Archive: `docs/archive/`

## Common Pitfalls

1. **WSL npm** — Always fails on /mnt/d. Use PowerShell for frontend.
2. **pip missing** — Use `uv pip install <pkg> --python .venv312/bin/python`
3. **curl + proxy** — WSL proxy interferes. Use `--noproxy '*'` for localhost.
4. **Import hangs** — `app.database.models.runtime` can hang 30s on first import. Retry.
5. **Design first** — Jumping to code without a design doc will be rejected.
6. **Data must be real** — Never fabricate business data. `data_available=false` → mock.
