# Industrial Park Agent 代码审计与优化报告 V1.1

审计日期：2026-07-22  
审计范围：前端、后端、LangGraph、Tool Gateway、数据库模型、认证、容器与运行文档。

## 1. 结论

优化后的工程已达到“比赛 Demo 可安装、可构建、核心流程可运行”的标准，但尚未达到生产上线标准。

| 维度 | 优化前 | 优化后 | 结论 |
| --- | --- | --- | --- |
| 后端依赖安装 | 失败 | 通过 | 修复 LangGraph/LangChain Core 版本冲突 |
| 前端生产构建 | Docker 必然失败 | 通过 | 增加 lockfile，改为 standalone 镜像 |
| Supervisor 调度 | 固定 Mock 结果 | 真实调用业务图 | 核心闭环已打通 |
| 复合意图 | 只识别第一个关键词 | 顺序识别多业务意图 | 可调度 4 个以上 Agent |
| Trace | 前端固定演示图 | 读取真实任务 Trace | 任务与链路一一对应 |
| 认证 | 查询参数、任意密码均可登录 | JSON 登录、密码校验、JWT 开关 | Demo 默认关闭强制鉴权 |
| CORS | `*` + credentials | 配置化白名单 | 满足基础安全要求 |
| 启动编排 | 缺失 | Docker Compose | 包含前端、后端、PostgreSQL/pgvector、Redis |
| 回归测试 | 0 | 5 | 覆盖健康、认证、招商、复合 Agent、Trace |

综合判断：比赛演示就绪度约 85%；生产上线就绪度约 50%。

## 2. 已修复的 P0/P1 问题

1. `langgraph==0.2.0` 与 `langchain==0.3.0` 依赖冲突，导致后端无法安装。现采用兼容组合并移除未直接使用的 `langchain` 包。
2. 前端 Dockerfile 使用 `npm ci`，原工程却缺少 `package-lock.json`。现已补齐锁文件。
3. 新版 LangGraph 禁止节点名与 State 字段同名。已修复 Supervisor、Industry、Risk、Service 图中的冲突。
4. 业务 State 缺少 `input` 字段，API 输入可能被 LangGraph 丢弃。已为所有业务图补齐输入通道。
5. Supervisor 的 Agent Router 原先只生成固定文本。现通过统一业务 Agent Executor 调用六类业务图，数据访问仍严格经过 Tool Gateway。
6. 复合问题原先只命中首个关键词。现按“产业分析 → 招商 → 风险 → 政策 → BI/服务”识别并执行多个意图。
7. 招商推荐结果缺少前端卡片需要的行业、地区、注册资本、匹配理由。现已补齐标准字段。
8. 每次聊天现生成独立 Task ID，避免同一会话的 Trace 相互覆盖。
9. 前端 Trace 页面现调用真实 Trace API，不再固定显示冠军 Demo 样例。
10. 移除全局篡改 `console.warn` 的脚本，避免隐藏真实运行告警。
11. 全站统一 AppLayout；此前只有园区总览页有导航框架，子页面会脱离整体布局。
12. API 默认采用同源 `/api/v1`，由 Next.js 转发到后端，避免部署后浏览器错误访问自身 `localhost:8000`。
13. 登录改为 JSON Body，错误密码返回 401；可通过 `AUTH_ENABLED=true` 强制保护业务 API。
14. 后端和前端容器均改为非 root 用户运行；后端增加健康检查。
15. 前端升级至 Next.js 16.2，并移除未使用的 ECharts 依赖；通过受控依赖覆盖消除已知 npm 审计告警。

## 3. 架构符合性

符合项：

- 保留 Supervisor → Business Agent → Tool Gateway → Tool → Return Result 的控制链。
- 业务 Agent 未直接访问数据库 Session。
- FastAPI 提供 Chat、Task、Trace、Status、Dashboard 和业务 API。
- LangGraph Checkpointer 能为当前进程保存任务状态并生成 Trace。
- 无 LLM Key 时可使用确定性兜底模式，便于比赛现场演示。

部分符合项：

- Policy Agent 具备检索流程，但当前 Tool Gateway 返回内置政策数据，不是真正的 PDF 解析、Embedding 与 pgvector 检索。
- 数据库已有主要业务表和运行表模型，但业务 Tool 尚未切换到真实 Repository/SQL 查询。
- JWT 已实现，RBAC 目前只有 `park_manager` 角色声明，没有细粒度权限矩阵。
- Redis 已进入部署编排，但尚未承担缓存、分布式锁或任务队列。

未完成项：

- Alembic 正式迁移版本、数据回滚策略和生产种子数据。
- PostgreSQL 持久化 Checkpointer；当前 MemorySaver 在进程重启后丢失 Task/Trace。
- WebSocket/SSE 流式执行。当前前端进度动画是演示动画，并非后端实时事件。
- 政策采集、PDF 解析、切片、Embedding、pgvector Retriever 的真实实现。
- 企业、风险、产业、工单等真实数据连接器。
- 完整 RBAC、用户表、密码哈希、刷新令牌、审计日志。
- 限流、幂等、任务取消、超时、重试和熔断。
- 浏览器 E2E、数据库集成测试、并发和性能测试。

## 4. 验证结果

已执行：

```text
python -m compileall backend/app backend/tests       PASS
pytest -q                                            5 passed
npm run build                                        PASS (11 routes)
npm audit --omit=dev                                 PASS (0 vulnerabilities)
FastAPI/Uvicorn application startup                  PASS
```

Docker CLI 在本次审计环境中不可用，因此未实际执行镜像构建；Dockerfile 与 Compose 已完成静态核对，建议在交付机上运行：

```bash
cp .env.example .env
docker compose build --no-cache
docker compose up
```

## 5. 下一阶段建议

优先顺序：

1. 用真实 Database Tool 替换 Tool Gateway 内置演示数据，并建立 Alembic V1 基线迁移。
2. 完成 Policy RAG 数据管道和 pgvector 检索测试，以 `policy_id/chunk_id/source` 提供可追溯引用。
3. 将 Supervisor Checkpointer 替换为 PostgreSQL，并让 Task/Trace API 在多实例部署中保持一致。
4. 增加 SSE 或 WebSocket 事件，让前端 Agent 进度来自后端真实节点事件。
5. 落地用户、角色、权限、审计日志与生产密钥管理。
6. 增加 Playwright E2E、PostgreSQL 集成测试、故障注入与 50/100 并发压测。

## 6. 关键运行约束

- 比赛现场建议保持 `DATABASE_ENABLED=false`，除非真实数据库与初始化已经完整演练。
- 无模型密钥时结果来自确定性 Agent/Tool 流程；这不是模型故障。
- 生产环境必须设置 `APP_ENV=production`、`AUTH_ENABLED=true`、非默认管理员密码和至少 32 位 JWT Secret。
- 当前内置企业与政策内容只可用于 Demo，不应被解释为最新或权威业务数据。
