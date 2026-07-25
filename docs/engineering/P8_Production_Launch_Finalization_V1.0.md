# P8 Production Launch & Competition Finalization V1.0

> **Industrial Park Agent v1.2 — Final Release Package**  
> **分支**: `feature/production-upgrade-v1.2`  
> **日期**: 2026-07-25  
> **Commit**: `d93e5c0`

---

## 一、真实数据接入规划

### 1.1 当前 Mock 数据 → 真实数据迁移路径

| 数据源 | 当前 | 升级目标 | 切换方式 | 优先级 |
|--------|------|---------|---------|--------|
| 企业数据 | Mock 5家机器人企业 | 天眼查/企查查 API | `ENTERPRISE_DATA_SOURCE=tianyancha` | P0 |
| 风险数据 | Mock 评分 | 天眼查风险事件接口 | 同企业数据配置 | P0 |
| 政策数据 | Mock 8条政策 | 政府网站爬取 + RAG | `POLICY_RAG_MODE=production` | P1 |
| 产业链数据 | 硬编码 JSON | 行业知识图谱 API | `INDUSTRY_DATA_SOURCE=external` | P2 |
| 用户认证 | Hardcoded admin | PostgreSQL users表 + bcrypt | `AUTH_ENABLED=true` | P4 |
| Agent状态 | MemorySaver | PostgreSQL Checkpointer | `DATABASE_ENABLED=true` | P2 |
| 实时事件 | REST轮询 | SSE Streaming | `STREAMING_ENABLED=true` | P3 |

### 1.2 切换命令

```bash
# 一键切换到生产模式
cd /www/wwwroot/industrial-park
cp .env.production .env
# 编辑 .env: 填入真实 API keys
./deploy.sh build
```

---

## 二、生产安全加固

### 2.1 必须修改项 (P5 + P4)

| # | 项目 | 当前 | 生产要求 | 状态 |
|---|------|------|---------|------|
| 1 | JWT_SECRET | `change-this` | 64字符随机字符串 | ⚠️ |
| 2 | ADMIN_PASSWORD | `admin` | 12+字符强密码 | ⚠️ |
| 3 | Password Hash | bcrypt (P5) | ✅ bcrypt with salt | ✅ |
| 4 | DeepSeek API Key | `***` | 真实 Key | ⚠️ |
| 5 | CORS Origins | `localhost:3000` | 生产域名 | ⚠️ |
| 6 | HTTPS | 未配置 | Nginx + Let's Encrypt | ⚠️ |
| 7 | Rate Limiting | 无 | FastAPI middleware | ⚠️ |
| 8 | DB Password | `industrial` | 强密码 | ⚠️ |

### 2.2 安全加固命令

```bash
# 生成随机 JWT secret
python3 -c "import secrets; print(secrets.token_hex(32))"

# 生成 bcrypt admin 密码
python3 -c "import bcrypt; print(bcrypt.hashpw(b'YourPassword', bcrypt.gensalt()).decode())"

# Docker secrets (生产环境)
echo "your-jwt-secret" | docker secret create jwt_secret -
```

---

## 三、Demo 场景固化

### 3.1 预设5个演示场景

| # | 场景 | 输入 | 调用Agent | 预期亮点 |
|---|------|------|----------|---------|
| 1 | 产业分析 | "分析广州机器人产业链缺口" | Industry | DAG展示产业链结构 |
| 2 | 招商推荐 | "推荐广州机器人产业招商目标企业" | Investment | Top5企业+评分 |
| 3 | 风险评估 | "评估广州数控的风险" | Risk | 风险雷达图+指标 |
| 4 | 政策匹配 | "查找广州机器人产业相关政策" | Policy | 四级政策匹配 |
| 5 | 综合任务 | "帮广州打造机器人产业园，分析产业链，推荐企业，评估风险，匹配政策" | All 6 | Multi-Agent并行 |

### 3.2 预输入指令（比赛前准备好）

打开 `/agent/chat` 页面，输入框预填场景5的综合指令。按 Enter 即可开始。

### 3.3 预热脚本

```bash
#!/bin/bash
# 比赛前 10 分钟执行 — 预热 LLM + 数据库连接
curl -s http://localhost:8000/api/v1/health
curl -s -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"分析广州机器人产业"}' > /dev/null
echo "Warmup done"
```

---

## 四、5分钟演示流程 V4.0 (v1.2版)

### Timeline

| 时间 | 幕 | 画面 | 台词要点 | v1.2新特性 |
|------|---|------|---------|-----------|
| 0:00-0:30 | 痛点 | 产业园主任桌面 | 三个"不知道" | — |
| 0:30-1:00 | 登场 | Agent Team页面 | "不是Chatbot，是AI运营团队" | RBAC角色标签 |
| 1:00-1:45 | 调度 | Chat页面+Agent面板 | Supervisor分解任务 | SSE实时Agent状态 |
| 1:45-2:15 | 结果 | Markdown报告 | 产业+企业+风险+政策 | P2 Checkpointer持久化 |
| 2:15-3:00 | Trace | DAG可视化 | "点击节点看详情" | DAGView live模式 |
| 3:00-3:45 | Dashboard | 驾驶舱 | KPI+AI洞察 | 6角色数据视图 |
| 3:45-4:30 | 商业模式 | 价值数据 | "7000+园区，百亿市场" | — |
| 4:30-5:00 | 结尾 | 金句+Slogan | "AI进园区，产业更智能" | — |

### 关键变化（v1.1 → v1.2）

1. **SSE实时Agent面板**: Agent执行时右侧面板由真实事件驱动（不再用setTimeout假动画）
2. **Checkpointer持久化**: 刷新页面后Agent状态不丢失（展示P2可靠性）
3. **RBAC角色**: 页面顶部显示当前登录角色标签（展示P4安全性）
4. **DAGView Live**: Trace页面实时构建DAG图（展示P3 Streaming）

---

## 五、最终交付包

### 5.1 交付物清单

```
industrial-park-v1.2/
├── backend/              # FastAPI + LangGraph 后端
│   ├── app/              # 应用代码 (40+ .py files)
│   ├── migrations/       # Alembic 迁移 (P5)
│   ├── alembic.ini       # 迁移配置
│   ├── Dockerfile        # 生产镜像
│   └── requirements.txt  # Python依赖
├── frontend/             # Next.js 16 前端
│   ├── src/              # 14 React组件
│   └── Dockerfile        # 生产镜像
├── docs/engineering/     # 工程文档 (50+ docs)
│   ├── P0-P7 Design Docs
│   └── P0-P7 Implementation Reports
├── docker-compose.yml    # 5服务编排
├── nginx.conf            # 反向代理 + SSE
├── .env.production       # 生产配置模板
├── deploy.sh             # 一键部署
├── e2e-test.sh           # E2E测试
└── README.md             # 项目说明
```

### 5.2 一键启动

```bash
git clone git@github.com:qujiangbao/1.1.git
cd 1.1
git checkout feature/production-upgrade-v1.2
cp .env.production .env
# 编辑 .env: 填入 DEEPSEEK_API_KEY
./deploy.sh build
./deploy.sh health
./e2e-test.sh
```

### 5.3 技术栈

```
Frontend:  Next.js 16 + Ant Design + TypeScript
Backend:   FastAPI + LangGraph 0.2.28
AI:        DeepSeek-chat (via LangChain OpenAI)
Database:  PostgreSQL 16 + pgvector + Redis 7
Auth:      JWT + bcrypt + RBAC (6 roles)
Storage:   Alembic migrations (17 tables)
Streaming: SSE (Server-Sent Events)
Deploy:    Docker Compose + Nginx
```

### 5.4 关键数据

| 指标 | 值 |
|------|-----|
| Agent数量 | 6 Business + Supervisor |
| 数据库表 | 17 (5 Business + 4 Runtime + 5 RBAC + 3 LangGraph) |
| 工具数量 | 18 (ToolGateway) |
| Intent路由 | 18 条映射 |
| RBAC角色 | 6 (SUPER_ADMIN → VIEWER) |
| 权限定义 | 14 permission codes |
| 后端代码行 | ~6,000+ |
| 前端组件 | 14 |
| 工程文档 | 50+ |
| P0-P7测试 | 300+ |

---

## 六、比赛日检查清单

### 赛前2小时
- [ ] Docker 环境确认 (`docker --version`)
- [ ] 构建镜像 (`./deploy.sh build`)
- [ ] 启动服务 (`./deploy.sh up`)
- [ ] 健康检查 (`./deploy.sh health`)
- [ ] E2E测试 (`./e2e-test.sh`)
- [ ] 预热LLM (跑一次综合任务)

### 赛前30分钟
- [ ] 浏览器隐身窗口全屏
- [ ] 预加载所有页面标签
- [ ] Agent Chat输入框预填综合指令
- [ ] 关闭所有通知

### 赛中
- [ ] 按5分钟脚本执行，不随意跳转
- [ ] 如LLM超时 → 等待3秒自动fallback
- [ ] 如前端崩溃 → 终端 curl 展示API响应
- [ ] 保持语速中等，有停顿

### 故障预案
| 故障 | Plan B | Plan C |
|------|--------|--------|
| DeepSeek API不可用 | LLM Gateway自动降级关键词 | 展示预录Demo视频 |
| 前端无法启动 | curl API + 终端展示 | 展示PPT+DAG截图 |
| Docker崩溃 | 直接 Python uvicorn | 预录视频 |

---

*Generated by Hermes Agent · 2026-07-25 · P8 Production Launch & Competition Finalization V1.0*
