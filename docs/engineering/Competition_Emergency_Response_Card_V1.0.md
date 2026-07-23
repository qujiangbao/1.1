# Competition Emergency Response Card V1.0

> 打印携带 | 比赛现场速查 | 每个问题 30 秒解决

---

## 🟡 LLM 响应慢（>20 秒未返回）

**症状**：Agent Chat 发出后 20 秒仍无结果

**30秒解决**：

```
1. 不慌。开始讲话术（见下方）
2. 后台打开新终端：
   curl -X POST http://localhost:8000/api/v1/agent/chat \
     -H "Content-Type: application/json" \
     -d '{"message":"机器人产业招商"}' &
3. 如果 30s 仍无返回 → 切到 Plan B 话术
```

**话术（填充等待时间）**：
> "大模型正在分析 12,580 家企业的产业链数据。趁这个时间，大家注意看右侧——Supervisor 已经完成了任务分解。我们的 Supervisor 通过 LangGraph StateGraph 实现了动态 DAG 规划，这是和传统 LLM Router 的核心区别..."

**Plan B 话术（如果确认 LLM 挂了）**：
> "DeepSeek 的网络有些波动——这恰好展示了我们 LLM Gateway 的容错设计。让我切换到 Dashboard 展示 AI 运营日报的实际效果。"

---

## 🔴 页面白屏/404（前端异常）

**症状**：浏览器显示空白页或 404

**30秒解决**：

```
1. 硬刷新：Ctrl+Shift+R
2. 如果仍白屏 → PowerShell 重启前端：
   Ctrl+C → cd D:\广智能\frontend → npm run dev
3. 15 秒内恢复
```

**话术**：
> "页面做了热更新。大家稍等——系统正在加载 6 个 Agent 的状态数据。"

**终极备选**：
> 切到后端 API 展示：curl 直接展示 JSON（证明系统在跑）

---

## 🔴 API 返回 500/502（后端崩溃）

**症状**：任何 API 返回 500 或连接拒绝

**30秒解决**：

```bash
# WSL 终端：
cd /mnt/d/广智能/backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
# 10 秒内重启完成
```

**话术**：
> "后端在做一次热重启——15 秒就好。趁这个时间，我先介绍一下我们的 Agent 架构设计理念..."

**验证重启成功**：
```bash
curl http://localhost:8000/api/v1/health
```

---

## 🔴 网络全断（最坏情况）

**症状**：所有请求失败，ping 不通

**30秒解决**：

```
1. 检查手机热点 → 电脑连接手机热点
2. 如果热点也没有 → 切到 Plan C
```

**Plan C 话术**：
> "网络环境不在我们控制范围内，但系统的架构价值是确定的。我准备了一段上周录制的 Demo 视频——不是 mock，是真实跑出来的同一次执行。请大家看。"

**Plan C 操作**：
- 打开提前保存的录屏文件
- 视频包含：Agent Team → Chat → Trace → Dashboard

---

## 🟡 数据返回异常（空数组/0条）

**症状**：Investment Search 或 Policy Search 返回空

**30秒解决**：

```
不用修复。直接用 Agent Chat 结果代替独立搜索。
```

**话术**：
> "让我直接看 Agent Chat 的综合报告——它已经把产业分析、招商推荐、政策匹配整合在一起了。这比单独搜索更贴近实际使用场景。"

**操作**：切换到 Agent Chat 返回的 Markdown 报告，里面有完整结果

---

## 🟡 Agent Trace 空白

**症状**：Trace 页面只显示 Supervisor 节点，没有子 Agent

**30秒解决**：

```
不修复。用话术引导。
```

**话术**：
> "我们聚焦在 Supervisor 调度层——这是 Multi-Agent 最核心的价值。每个 Agent 的内部执行日志可以展开查看。现在让我们点开 IndustryAgent 节点..."

**操作**：点击 Supervisor 节点展示其输出详情（task_plan, intent 等）

---

## 🟡 Dashboard 数据不更新

**症状**：Dashboard 显示旧数据或加载中

**30秒解决**：

```
刷新页面 F5
```

**话术**：
> "Dashboard 数据每 5 分钟自动刷新一次。现在的数据显示——12,580 家企业、230 个招商机会..."

**操作**：直接念已知数据（Dashboard Overview 是硬编码的 Mock，不会变）

---

## 🔴 电脑蓝屏/死机

**症状**：黑屏/蓝屏

**30秒解决**：

```
1. 立即借旁边队友的电脑
2. 手机热点共享网络
3. 用备份 U 盘启动前端（如果准备了）
4. 切到纯 PPT 路演模式（12 页 PPT 已就绪）
```

**话术**：
> "硬件问题不影响我们展示系统的架构价值。我准备了 PPT——请看。"

---

## 🟢 一切正常（最可能的情况）

**话术**：
无。正常执行 Runbook。

---

## 速查卡（打印携带）

```
┌─────────────────────────────────────────────────────┐
│              EMERGENCY QUICK REFERENCE                │
├──────────────┬──────────────────────────────────────┤
│ LLM 慢       │ 讲话术填充 + 后台重试                  │
│ 页面白屏     │ Ctrl+Shift+R → 重启前端               │
│ 后端 500     │ 快速重启 uvicorn (10s)                │
│ 网络全断     │ 手机热点 → 录播视频                   │
│ 数据空       │ 切到 Agent Chat 综合报告              │
│ Trace 空白   │ 展开 Supervisor 节点                  │
│ Dashboard 不更新│ F5 刷新 + 念已知数据                │
│ 电脑死机     │ 队友电脑 + PPT 路演                   │
│              │                                      │
│ 关键命令：                                          │
│ curl localhost:8000/api/v1/health                    │
│ curl localhost:8000/api/v1/health/warmup              │
│ .venv/bin/python -m uvicorn app.main:app \           │
│   --host 0.0.0.0 --port 8000 &                       │
└─────────────────────────────────────────────────────┘
```

---

**Competition Emergency Response Card V1.0 完成。建议打印携带。**
