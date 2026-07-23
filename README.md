# Industrial Park Agent Competition Gold v1.1

广州产业 AI 运营官的可运行工程版：Next.js 15 前端、FastAPI 后端、LangGraph Supervisor、6 个业务 Agent、Tool Gateway，以及 PostgreSQL/pgvector 与 Redis 的容器编排。

## 一键启动

```bash
cp .env.example .env
docker compose up --build
```

启动后访问：

- 前端：http://localhost:3000
- API：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/v1/health

不配置模型密钥时，系统使用确定性的本地兜底逻辑，完整 Demo 仍可运行。配置 OpenAI 或 DeepSeek 密钥后，Supervisor 会使用模型完成意图识别与最终报告生成。

## 本地开发

后端：

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm ci
npm run dev
```

## 验证

```bash
cd backend
pytest -q

cd ../frontend
npm run build
```

## 运行模式说明

- `DATABASE_ENABLED=false`：比赛 Demo 模式，业务 Agent 通过 Tool Gateway 的内置演示数据运行。
- `DATABASE_ENABLED=true`：初始化当前 SQLAlchemy 模型并连接 PostgreSQL；生产环境仍应补充正式 Alembic 迁移和真实数据工具实现。
- `AUTH_ENABLED=false`：保持比赛演示开箱即用；生产部署必须启用认证、替换管理员密码和至少 32 位 `JWT_SECRET`。

详细审计结论见 `docs/engineering/Code_Audit_Optimization_Report_V1.1.md`。
