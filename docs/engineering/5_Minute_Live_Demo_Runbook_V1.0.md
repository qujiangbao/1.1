# 5 Minute Live Demo Runbook V1.0

> 版本：V1.0 | 时长：5 分钟 | 模式：逐秒操作手册
> "If anything can go wrong, this runbook tells you what to do."

---

## 零、启动序列（比赛前 10 分钟）

### Step 0: 启动后端（WSL）

```bash
cd /mnt/d/广智能/backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

等待看到：
```
INFO:  Uvicorn running on http://0.0.0.0:8000
INFO:  [Warmup] Background warmup task scheduled
```

### Step 1: 启动前端（Windows PowerShell）

```powershell
cd D:\广智能\frontend
npm run dev
```

等待看到：
```
ready - started server on http://localhost:3000
```

### Step 2: 验证 Warmup（WSL）

```bash
# 等待 25 秒让 Warmup 完成
sleep 25
curl http://localhost:8000/api/v1/health/warmup
```

期望输出：
```json
{"status":"ready","llm_ready":true,...}
```

### Step 3: 打开浏览器标签页

在 Chrome 无痕模式中打开 4 个标签页：

```
Tab 1: http://localhost:3000/agent/team     ← Agent Team 页面
Tab 2: http://localhost:3000/agent/chat      ← AI 运营中心（预输入 Demo 指令）
Tab 3: http://localhost:3000/dashboard       ← Dashboard
Tab 4: 留空（Trace 跳转用）
```

**在 Tab 2 的输入框中预输入 Demo 指令——不要按 Enter：**

```
帮广州打造机器人产业园，分析产业链缺口，推荐招商目标企业，评估风险，匹配政策支持
```

---

## 一、演示步骤（秒级）

### 0:00-0:30 | Step A: Agent Team 展示

**操作**：切换到 Tab 1 (`/agent/team`)

**画面**：6 张 Agent 卡片，全部绿色"在线"

**台词**：
> "各位评委好。这是广州产业AI运营官——不是 Chatbot，是一支 6 个 AI 同事组成的运营团队。每个 AI 有独立的职责和能力。接下来，我给他们一个任务。"

---

### 0:30-1:00 | Step B: 发布任务

**操作**：切换到 Tab 2 (`/agent/chat`) → 光标已在输入框 → 检查预填文本 → 按 **Enter**

**画面**：右侧 Agent 状态面板开始变化

**台词**：
> "我只需要说一句话——帮广州打造机器人产业园。现在看右侧——Supervisor，也就是 AI 运营总经理，正在分析我的意图。"

---

### 1:00-1:45 | Step C: Agent 协作（等待期间）

**操作**：不操作，让 Agent 自动执行

**画面**：右侧面板逐个显示 Agent 状态变化

**台词**（穿插，不要一直说，让动画说话）：
> "Supervisor 拆了 3 个子任务：产业分析、风险评估、政策匹配。注意——RiskAgent 和 PolicyAgent 会同时启动，这是真正的并行执行。"

**如果 15 秒后还没返回**（极少发生，Warmup 后稳定 12-15s）：
> "大模型正在深度分析产业链数据。趁这个时间，大家注意看——右侧面板已经展示了 Supervisor 的任务分解结果。"

---

### 1:45-2:15 | Step D: 查看结果

**操作**：结果返回后，鼠标滚动左侧 Markdown 报告

**画面**：招商报告（产业分析 + 企业推荐 + 风险评估 + 政策建议）

**台词**：
> "15 秒，6 个 Agent 协作完成。传统团队 2 周的工作。现在看结果——产业分析、招商推荐、风险评估、政策支持，一条龙。"

---

### 2:15-3:00 | Step E: Agent Trace DAG

**操作**：点击页面上的"查看执行链路"按钮（或手动导航到 `/agent/trace/{taskId}`）

**画面**：DAG 图展示 Supervisor → Agent 的调用链

**台词**：
> "这是全链路 Trace——每一步都可追溯。Supervisor → IndustryAgent → RiskAgent + PolicyAgent 并行。每个节点可以点击查看输入输出和耗时。这就是 Multi-Agent 和单 LLM 的本质区别。"

**操作**：点击 2 个节点展示详情

---

### 3:00-3:45 | Step F: Dashboard

**操作**：切换到 Tab 3 (`/dashboard`)

**画面**：KPI 卡片 + AI 运营日报

**台词**：
> "这是 AI 运营驾驶舱。12,580 家企业、230 个招商机会、AI 每天自动分析。不是数据罗列——是带判断、带建议的行动清单。园区主任每天早上打开这个页面，就知道今天该做什么。"

---

### 3:45-5:00 | Step G: 商业价值 + 结尾

**操作**：切回 Tab 1 或空白页，全屏大字

**台词**：
> "最后三件事。第一，我们有真实数据——1050 家机器人企业、55 条政策。第二，成本——传统 50 万一年，AI 不到 10 万。第三，市场——中国 7,000+ 产业园，我们是第一个 AI 原生方案。"
>
> "我们的使命：不是做一个工具。而是让每一个产业园，都拥有一支 7×24 小时的 AI 运营团队。"
>
> "**广州产业AI运营官——AI 进园区，产业更智能。** 谢谢！"

---

## 二、标签页切换速查

| 时间 | 操作 | 目标标签页 | 热键 |
|------|------|-----------|:---:|
| 0:00 | 展示 Agent Team | Tab 1 | Ctrl+1 |
| 0:30 | 发布 Demo 任务 | Tab 2 → Enter | Ctrl+2 |
| 1:45 | 滚动结果 | Tab 2 | — |
| 2:15 | Trace DAG | Tab 4 (跳转) | — |
| 3:00 | Dashboard | Tab 3 | Ctrl+3 |
| 3:45 | 结尾 | 任意 | — |

---

## 三、关键时间节点

| 时刻 | 检查点 | 如果超时 |
|------|--------|---------|
| T+3s | Agent 面板开始变化 | 检查后端是否在运行 |
| T+5s | Supervisor 识别完成 | 正常 |
| T+15s | Agent Chat 返回结果 | 开始讲"大模型正在深度分析"话术 |
| T+20s | ⚠️ 仍未返回 | 使用 Emergency Card: LLM慢 |

---

## 四、演示前检查清单

```
□ 后端运行中（curl /health → healthy）
□ Warmup 完成（curl /health/warmup → llm_ready:true）
□ 前端运行中（localhost:3000 可访问）
□ Chrome 无痕模式，4 个标签页就绪
□ Tab 2 输入框预填 Demo 指令
□ 系统通知全部关闭
□ 投影分辨率 1920×1080 测试通过
□ 网络可访问 api.deepseek.com
□ 手机热点备用网络就绪
```

---

## 五、场地适应

如果投影是 4:3 而非 16:9：
- 浏览器缩放到 90%
- 或将 Chrome DevTools 切换为移动端模拟 (375px 宽)

如果网络延迟高：
- Warmup 已经解决了大部分延迟
- 如果 Agent Chat > 20s，使用 LLM 慢话术

---

**5 Minute Live Demo Runbook V1.0 完成。**
