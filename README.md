# 智园领航——AI 产业园运营平台

面向产业园区招商、政策、风险与日常运营决策的多智能体平台。Supervisor 负责理解需求、规划任务和汇总结果，并调度产业研究、招商决策、企业风险、政策顾问、企业服务和 BI 分析六个业务 Agent。

系统坚持证据边界：缺少权威字段时显示“待补证/尚未评估”，不会把缺失值当成零分，也不会把演示数据冒充真实经营数据。政策检索与资格判断分离，未经人工审核或没有政策原文依据的结构化规则不参与资格计算。

## 核心能力

- 园区决策工作台：多 Agent 协作、任务状态和 Trace 追踪。
- 招商决策中心：企业筛选、证据卡片、数据缺口、政策候选与 CRM 跟进。
- 政策服务：政府政策检索、原文追溯，以及基于已审核政策原文规则的全园区企业资格匹配。
- 政策更新中心：初始管理员授权、政府域名白名单、增量抓取、正文指纹和版本去重。
- 园区资料库：导入 PDF、DOCX、PPTX、TXT 和 Markdown；文件与正文双重去重；结构化补充企业和风险证据。
- 运营与风险看板：汇总任务、企业、政策、招商漏斗和已导入风险证据。

## 技术架构

```text
Browser
  │
Nginx :8080
  ├── Next.js 16 / React 19 / Ant Design
  └── FastAPI / LangGraph Supervisor
        ├── 6 个业务 Agent + Tool Gateway
        ├── PostgreSQL 16 + pgvector
        ├── Redis 7
        └── DeepSeek / OpenAI-compatible LLM Gateway
```

生产部署使用 Docker Compose；后端运行在 Python 3.12，前端使用 Node.js 22。

## 本地开发

复制开发配置：

```powershell
Copy-Item .env.example .env
```

后端（Windows + WSL 示例）：

```bash
cd /mnt/d/industrial-park-v1.1/backend
python3.12 -m venv .venv312
.venv312/bin/python -m pip install -r requirements-dev.txt
.venv312/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端（PowerShell）：

```powershell
Set-Location D:\industrial-park-v1.1\frontend
npm ci
npm run dev
```

开发地址：

- 前端：http://localhost:3000
- API 文档：http://localhost:8000/docs
- Liveness：http://localhost:8000/api/v1/health/live
- Readiness：http://localhost:8000/api/v1/health/ready

## 生产部署

```powershell
Copy-Item .env.production.example .env.production
# 将所有 replace-with- 占位值替换为真实强密码或密钥
docker compose --env-file .env.production up -d --build
```

生产配置会强制要求数据库、认证、至少 32 字符的 JWT 密钥、明确的 CORS 来源和非占位密码。不要提交 `.env.production`、园区私有资料、企业快照或政策全文快照。

## 园区资料导入约束

- 支持：PDF、DOCX、PPTX、TXT、Markdown。
- 单文件上限：25 MB。
- Office 文件会校验真实 ZIP 结构、成员数量和解压后大小；PDF 会校验文件签名和页数。
- 提取正文设有安全上限；重复文件或正文不会再次入库。
- 导入分类包括园区规划、招商资料、企业资料、政策文件、会议纪要和园区综合资料。

## 质量验证

```bash
# 后端
cd backend
.venv312/bin/python -m ruff check app tests
.venv312/bin/python -m pip_audit -r requirements.txt
.venv312/bin/python -m pytest -q
```

```powershell
# 前端
Set-Location frontend
npm audit --omit=dev
npm run typecheck
npm run build
```

GitHub Actions 会在 push 和 pull request 时执行相同质量门禁，Dependabot 每周检查 Python、npm 和 Actions 依赖。

## 文档

- [系统架构](docs/ARCHITECTURE.md)
- [项目上下文](docs/PROJECT_CONTEXT.md)
- [文档索引](docs/doc-index.md)
- [Agent 索引](docs/agent-index.md)
- [政策更新中心使用说明](docs/政策更新中心使用说明.md)

## 数据与合规

仓库只应包含源码、迁移、测试和配置模板。生产密钥、园区私有资料、真实企业数据和政策全文快照必须通过部署环境或系统导入，不得进入 Git。公开数据也应保留来源 URL、采集时间和处理记录，AI 结论必须允许人工复核。
