# 广州产业AI运营官 v1.2

> **Industrial Park Agent** — 12-Agent Multi-Agent AI System for Industrial Park Operations  
> 2026 Super Agent 大赛 · Gold Release Candidate

## Quick Start

```bash
git clone git@github.com:qujiangbao/1.1.git
cd 1.1
git checkout feature/production-upgrade-v1.2
cp .env.production .env
# Edit .env: add DEEPSEEK_API_KEY
./deploy.sh build
```

## Architecture

```
User → Nginx :80 → Next.js :3000 + FastAPI :8000
                        ↓
            Supervisor (LangGraph StateGraph)
           ↙    ↓    ↓    ↓    ↓    ↘
    Industry  Investment  Risk  Policy  Service  BI
           ↘    ↓    ↓    ↓    ↓    ↙
              ToolGateway (18 tools)
                    ↓
         PostgreSQL/pgvector + Redis
```

## Features (P0-P7)

| Phase | Feature | Status |
|-------|---------|--------|
| P0 | Enterprise Data Tool | ✅ |
| P1 | Policy RAG + pgvector | ✅ |
| P2 | LangGraph Checkpointer (PostgreSQL) | ✅ |
| P3 | SSE Real-Time Streaming | ✅ |
| P4 | RBAC (6 roles) | ✅ |
| P5 | Alembic Migrations + bcrypt | ✅ |
| P6 | Docker Production Deployment | ✅ |
| P7 | System Acceptance (144/144) | ✅ |

## Tech Stack

- **Frontend**: Next.js 16 + Ant Design + TypeScript
- **Backend**: FastAPI + LangGraph 0.2.28
- **AI**: DeepSeek-chat
- **Database**: PostgreSQL 16 + pgvector + Redis 7
- **Auth**: JWT + bcrypt + RBAC
- **Streaming**: SSE (Server-Sent Events)
- **Deploy**: Docker Compose + Nginx
- **Migration**: Alembic

## Docs

See `docs/engineering/` for all design docs and implementation reports.
