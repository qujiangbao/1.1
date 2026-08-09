# Industrial Park Agent — 广州产业 AI 运营官

> **不是 Chatbot，是一支 7×24 小时工作的 AI 产业运营团队。**
>
> 替代传统：招商团队、政策咨询团队、企业服务团队、产业研究团队、风险管理团队。

> 数据安全说明：本仓库仅发布源码、数据库迁移、测试和配置模板。生产密钥、园区私有资料、企业快照及政策全文快照不会进入 Git；请在部署后通过园区资料库和政策同步工具导入。

---

## 架构概览

```
                    User / Browser
                         |
                  Nginx :80 (reverse proxy)
                    /        \
                   /          \
        Next.js :3000       FastAPI :8000
        (Ant Design)        (API Gateway)
                                 |
                    LangGraph Supervisor (7 nodes)
                   /    |    |    |    |    \
                  /     |    |    |    |     \
           Industry Investment Risk Policy Service  BI
           Agent    Agent    Agent Agent  Agent   Agent
                  \     |    |    |    |    /
                   \    |    |    |    |   /
                    Tool Gateway (18 tools, RBAC)
                           |
              PostgreSQL 16 + pgvector + Redis 7
```

## 技术栈

| 层级 | 技术 |
|------|------|
| AI 编排 | LangGraph (StateGraph) |
| 后端 | FastAPI (Python 3.12) |
| 前端 | Next.js 16 + React + Ant Design |
| 数据库 | PostgreSQL 16 + pgvector 0.8.5 |
| 缓存 | Redis 7 |
| LLM | DeepSeek V4 |
| 部署 | Docker Compose + Nginx |

## 快速启动

### 后端（WSL/Linux 必须）

```bash
cd /mnt/d/industrial-park-v1.1/backend
uv pip install -r requirements.txt --python .venv312/bin/python
PYTHONPATH=. .venv312/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端（Windows PowerShell 必须）

```powershell
cd D:\industrial-park-v1.1\frontend
npm ci
npm run dev
```

### 开发地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| API 文档 | http://localhost:8000/docs |
| Liveness | http://localhost:8000/api/v1/health/live |
| Readiness | http://localhost:8000/api/v1/health/ready |

### 生产部署

```bash
cp .env.production.example .env.production
# 替换 .env.production 中全部 replace-with- 值
./deploy.sh up
```

## Agent 团队

| Agent | 角色 | 一句话职责 |
|-------|------|-----------|
| **Supervisor** | AI 运营总经理 | 意图识别 → 任务规划 → Agent 路由 → 结果聚合 |
| **Policy** | AI 政策顾问 | PDF 解析 → 向量检索 → 政策匹配 → 申报建议 |
| **Investment** | AI 招商经理 | 企业搜索 → 画像 → 评分 → 推荐 → 策略 |
| **Industry** | AI 产业研究院 | 产业链分析 → 趋势预测 → 招商方向 |
| **Risk** | 企业风险雷达 | 6 维风险评分（经营/财务/舆情/法律/人才/市场） |
| **Service** | AI 企业管家 | 需求理解 → 服务分类 → 工单管理 |
| **BI** | AI 数字驾驶舱 | 5 大维度 30+ KPI 可视化 |

## 数据管道

```
政策管道：
  gz.gov.cn → Crawl4AI (offline) → Markdown cache (222 docs)
    → PolicyRetriever → pgvector (HNSW) → PolicyAgent

企业管道：
  天眼查/企查查 → Enterprise Adapters → PostgreSQL
    → EnterpriseTool → InvestmentAgent/RiskAgent
```

## 文档体系

| 文档 | 用途 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构唯一事实来源（FROZEN） |
| [doc-index.md](docs/doc-index.md) | 完整文档索引 |
| [agent-index.md](docs/agent-index.md) | Agent 职责与设计文档索引 |
| [CODEBUDDY.md](CODEBUDDY.md) | AI 开发助手上下文 |
| `docs/architecture/` | 冻结设计规范 |
| `docs/agents/` | Agent 详细设计 |
| `docs/engineering/` | 工程实施文档 |
| `docs/archive/` | 历史版本归档 |

## 版本历史

| 版本 | 日期 | 状态 | 说明 |
|------|------|:---:|------|
| V1.0 | 2026-07-21 | ARCHIVE | 12 Agent 架构设计完成 |
| V1.1 | 2026-07-22 | FREEZE | 比赛金奖版（main 分支） |
| V1.2 | 2026-07-25 | — | P0-P8 生产升级 |
| **V1.3** | **2026-07-28** | **CURRENT** | Crawl4AI 政策集成 + 生产稳定 |

## 验证

```bash
# 后端
cd backend && PYTHONPATH=. .venv312/bin/python -m pytest -q

# 前端
cd frontend && npm run build

# E2E
./warmup.sh http://localhost:8000
./e2e-test.sh http://localhost:8000
```

## 约束

- 前端 **必须** 在 Windows PowerShell 运行（WSL npm on /mnt/d 超时）
- 后端 **必须** 在 WSL/Linux 运行
- `main` 分支永久冻结（V1.1 比赛金奖版）
- Agent 接口 `execute_business_agent()` 签名不可变
- Supervisor 7 节点不可增删
- 使用 `uv pip install`，非 `pip`
- 数据不得伪造：`data_available=false` 时用 mock，不填假数字

---

**Industrial Park Agent — 让 AI 运营一座产业园。**
