"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Input,
  Space,
  Steps,
  Tag,
  Typography,
} from "antd";
import {
  AimOutlined,
  BarChartOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DashboardOutlined,
  FileTextOutlined,
  LoadingOutlined,
  NodeIndexOutlined,
  PlayCircleOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiJson, resolveApiUrl } from "@/api/fetch";
import { createScenario, getRecommendations } from "@/api/investment.api";
import { useDataMode } from "@/contexts/DataModeContext";

const { Title, Text } = Typography;
const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
const DEFAULT_MESSAGE =
  "帮广州打造机器人产业园，分析产业链缺口，推荐招商目标企业，评估风险，匹配政策支持";

interface AgentNode {
  name: string;
  display: string;
  icon: string;
  role: string;
  status: "pending" | "running" | "completed" | "failed";
  action?: string;
}

interface ChatStartResponse {
  task_id: string;
  status: string;
  response?: string | null;
  stream_url?: string | null;
  agents_used?: string[];
  trace_id?: string;
}

const INITIAL_AGENTS: AgentNode[] = [
  { name: "Supervisor", display: "AI运营总经理", icon: "👔", role: "统筹调度", status: "pending" },
  { name: "IndustryAgent", display: "AI产业研究院", icon: "🔬", role: "产业分析", status: "pending" },
  { name: "InvestmentAgent", display: "AI招商经理", icon: "💼", role: "企业发现", status: "pending" },
  { name: "RiskAgent", display: "企业风险雷达", icon: "🛡️", role: "风险评估", status: "pending" },
  { name: "PolicyAgent", display: "AI政策顾问", icon: "📋", role: "政策匹配", status: "pending" },
  { name: "EnterpriseServiceAgent", display: "AI企业服务助手", icon: "🏢", role: "服务咨询", status: "pending" },
  { name: "BIAgent", display: "AI经营分析师", icon: "📊", role: "经营分析", status: "pending" },
];

const cloneInitialAgents = () => INITIAL_AGENTS.map((agent) => ({ ...agent }));

const INDUSTRY_KEYWORDS = [
  "机器人", "人工智能", "生物医药", "新能源汽车", "半导体", "芯片",
  "新材料", "高端装备", "智能制造", "低空经济", "氢能", "储能",
  "物联网", "大数据", "云计算", "5G", "量子计算", "区块链",
];

const CITY_NAMES = [
  "广州", "深圳", "东莞", "佛山", "珠海", "惠州", "中山",
  "粤港澳大湾区", "珠三角", "长三角", "京津冀",
];

function extractContext(text: string) {
  const industry = INDUSTRY_KEYWORDS.find((kw) => text.includes(kw)) || "机器人";
  const location = CITY_NAMES.find((city) => text.includes(city)) || "广州";
  const roles = ["核心零部件", "系统集成", "工业软件"];
  return { industry, location, roles };
}

function buildAgentRoute(
  agentName: string,
  context: { industry: string; location: string; roles: string[] },
): { path: string; label: string } {
  const enc = (s: string) => encodeURIComponent(s);
  switch (agentName) {
    case "Supervisor":
      return { path: "/agent/team", label: "查看智能体团队" };
    case "IndustryAgent":
      return {
        path: `/agent/chat?prompt=${enc(`请深度分析${context.industry}产业链趋势、关键缺口和招商机会，并给出目标企业画像建议`)}`,
        label: "产业深度分析",
      };
    case "InvestmentAgent":
      return {
        path: `/dashboard/investment?industry=${enc(context.industry)}&roles=${enc(context.roles.join(","))}&location=${enc(context.location)}`,
        label: "招商决策中心",
      };
    case "RiskAgent":
      return { path: "/dashboard/risk", label: "企业风险监测" };
    case "PolicyAgent":
      return { path: "/management/policies", label: "惠企政策库" };
    case "EnterpriseServiceAgent":
      return { path: "/agent/chat", label: "企业服务咨询" };
    case "BIAgent":
      return { path: "/dashboard/bi", label: "经营分析看板" };
    default:
      return { path: "/dashboard", label: "园区运营总览" };
  }
}

function getAgentTooltip(agent: AgentNode): string | null {
  if (agent.status !== "completed") return null;
  return `点击跳转：${buildAgentRoute(agent.name, { industry: "机器人", location: "广州", roles: [] }).label}`;
}

export default function AgentWorkspacePage() {
  const router = useRouter();
  const { mode, isDemo } = useDataMode();
  const [input, setInput] = useState(DEFAULT_MESSAGE);
  const [running, setRunning] = useState(false);
  const [currentPhase, setCurrentPhase] = useState(-1);
  const [agents, setAgents] = useState<AgentNode[]>(cloneInitialAgents);
  const [response, setResponse] = useState("");
  const [taskId, setTaskId] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [usedAgents, setUsedAgents] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [investScenarioId, setInvestScenarioId] = useState("");
  const [investReady, setInvestReady] = useState(false);
  const streamRef = useRef<EventSource | null>(null);

  useEffect(() => () => {
    streamRef.current?.close();
    streamRef.current = null;
  }, []);

  // Persist completed task state to sessionStorage so it survives page navigation
  const STORAGE_KEY = "workspace_last_task";
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        setInput(parsed.input || DEFAULT_MESSAGE);
        setResponse(parsed.response || "");
        setTaskId(parsed.taskId || "");
        setUsedAgents(parsed.usedAgents || []);
        setElapsed(parsed.elapsed || 0);
        setCurrentPhase(parsed.response ? 3 : -1);
        if (parsed.agents) {
          setAgents(parsed.agents);
        }
      }
    } catch { /* ignore corrupt storage */ }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (response && !running) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        input, response, taskId, usedAgents, elapsed, agents,
      }));
    }
  }, [response, running, hydrated]);

  const finishAgents = useCallback((used: string[]) => {
    setAgents((previous) =>
      previous.map((agent) => ({
        ...agent,
        status:
          agent.name === "Supervisor" || used.includes(agent.name)
            ? "completed"
            : "pending",
        action:
          agent.name === "Supervisor"
            ? `调度 ${used.length} 个 Agent 完成`
            : used.includes(agent.name)
              ? "已参与本次任务"
              : "本次未调用",
      })),
    );
  }, []);

  const runTask = useCallback(async () => {
    const message = input.trim();
    if (!message || running) return;

    sessionStorage.removeItem(STORAGE_KEY);
    setInvestScenarioId("");
    setInvestReady(false);
    const startedAt = performance.now();
    setRunning(true);
    setError("");
    setResponse("");
    setTaskId("");
    setUsedAgents([]);
    setElapsed(0);
    setCurrentPhase(0);
    setAgents(
      cloneInitialAgents().map((agent) =>
        agent.name === "Supervisor"
          ? { ...agent, status: "running", action: "正在分析需求并编排任务..." }
          : agent,
      ),
    );

    let streamingStarted = false;
    try {
      const data = await apiJson<ChatStartResponse>(`${API}/agent/chat`, {
        method: "POST",
        body: JSON.stringify({ message, context: { data_mode: mode } }),
      });
      setTaskId(data.task_id);

      if (data.stream_url) {
        streamingStarted = true;
        setCurrentPhase(2);
        let terminal = false;
        const eventSource = new EventSource(resolveApiUrl(data.stream_url, API));
        streamRef.current?.close();
        streamRef.current = eventSource;
        const closeStream = () => {
          eventSource.close();
          if (streamRef.current === eventSource) streamRef.current = null;
        };

        eventSource.addEventListener("snapshot", (event) => {
          const snapshot = JSON.parse((event as MessageEvent).data);
          const results = snapshot.agent_results || {};
          const planned = new Set(
            (snapshot.task_plan || []).map((task: { agent?: string }) => task.agent),
          );
          setCurrentPhase(snapshot.task_plan?.length ? 2 : 1);
          setAgents((previous) =>
            previous.map((agent) => {
              if (agent.name === "Supervisor") {
                return { ...agent, status: "running", action: "正在汇总 Agent 结果..." };
              }
              const result = results[agent.name];
              if (result) {
                return {
                  ...agent,
                  status: result.status === "failed" ? "failed" : "completed",
                  action:
                    result.summary ||
                    (result.status === "failed" ? "执行失败" : "已完成"),
                };
              }
              return planned.has(agent.name)
                ? { ...agent, status: "running", action: "已进入任务计划" }
                : agent;
            }),
          );
        });

        eventSource.addEventListener("done", (event) => {
          terminal = true;
          const parsed = JSON.parse((event as MessageEvent).data);
          const payload = parsed.payload || {};
          const used: string[] = payload.agents_used || [];
          setResponse(payload.final_response || "任务已完成，但后端未返回报告内容。");
          setUsedAgents(used);
          setTaskId(payload.task_id || data.task_id);
          setElapsed(Math.round((performance.now() - startedAt) / 100) / 10);
          setCurrentPhase(3);
          finishAgents(used);
          setRunning(false);
          closeStream();

          // 后台自动创建招商场景，让驾驶舱立即可用
          if (used.includes("InvestmentAgent")) {
            const ctx = extractContext(message);
            createScenario({
              name: `${ctx.industry}产业招商研判`,
              industry: ctx.industry,
              target_chain_roles: ctx.roles,
              location_preference: ctx.location,
              limit: 5,
              data_mode: mode,
            })
              .then((scenario) => {
                setInvestScenarioId(scenario.scenario_id);
                setInvestReady(true);
              })
              .catch(() => setInvestScenarioId(""));
          }
        });

        eventSource.addEventListener("error", (event) => {
          if (terminal || !(event instanceof MessageEvent)) return;
          terminal = true;
          const parsed = JSON.parse(event.data);
          const messageText = parsed.payload?.message || "Agent 执行失败";
          setError(messageText);
          setAgents((previous) =>
            previous.map((agent) =>
              agent.name === "Supervisor"
                ? { ...agent, status: "failed", action: messageText }
                : agent,
            ),
          );
          setRunning(false);
          closeStream();
        });

        eventSource.onerror = () => {
          if (terminal) return;
          terminal = true;
          setError("实时连接中断，请重新启动任务。");
          setAgents((previous) =>
            previous.map((agent) =>
              agent.name === "Supervisor"
                ? { ...agent, status: "failed", action: "实时连接中断" }
                : agent,
            ),
          );
          setRunning(false);
          closeStream();
        };
        return;
      }

      const used = data.agents_used || [];
      setResponse(data.response || "任务已完成，但后端未返回报告内容。");
      setUsedAgents(used);
      setElapsed(Math.round((performance.now() - startedAt) / 100) / 10);
      setCurrentPhase(3);
      finishAgents(used);
    } catch (caught) {
      sessionStorage.removeItem(STORAGE_KEY);
      const messageText = caught instanceof Error ? caught.message : "未知错误";
      setError(messageText);
      setAgents((previous) =>
        previous.map((agent) =>
          agent.name === "Supervisor"
            ? { ...agent, status: "failed", action: messageText }
            : agent,
        ),
      );
    } finally {
      if (!streamingStarted) setRunning(false);
    }
  }, [finishAgents, input, mode, running]);

  const completedCount = agents.filter((agent) => agent.status === "completed").length;
  const phases = [
    { title: "意图识别", description: "Supervisor 分析需求", icon: <AimOutlined /> },
    { title: "任务规划", description: "生成实际执行计划", icon: <NodeIndexOutlined /> },
    { title: "Agent 协作", description: "按后端状态执行", icon: <TeamOutlined /> },
    { title: "决策报告", description: "返回真实生成结果", icon: <BulbOutlined /> },
  ];

  return (
    <div className="workspace-shell">
      <section className="workspace-hero">
        <div className="workspace-hero-copy">
          <span className="workspace-hero-kicker">AI DECISION ORCHESTRATION</span>
          <h1>把园区问题交给一支 AI 运营团队</h1>
          <p>
            输入一个目标，由 Supervisor 自动拆解任务，并调度产业、招商、风险、政策与 BI Agent 协同完成。
            {isDemo ? " 当前为固定合成演示场景。" : " 当前使用公开数据快照，无依据内容保持待核验。"}
          </p>
        </div>
        <div className="workspace-hero-status" aria-label="工作台状态">
          <div className="workspace-status-item"><strong>6</strong><span>专业智能体</span></div>
          <div className="workspace-status-item"><strong>{completedCount}</strong><span>本轮已完成</span></div>
          <div className="workspace-status-item"><strong>{response ? `${elapsed}s` : "—"}</strong><span>本轮耗时</span></div>
          <div className="workspace-status-item"><strong>{running ? "运行" : "待命"}</strong><span>调度状态</span></div>
        </div>
      </section>

      {error && (
        <Alert
          type="error"
          showIcon
          closable
          message="任务执行失败"
          description={error}
          onClose={() => setError("")}
          style={{ marginBottom: 16 }}
        />
      )}

      <section className="workspace-command">
        <div className="workspace-command-head">
          <div className="workspace-command-title">
            <span><AimOutlined /></span>
            <div><div>描述你的园区目标</div><small style={{ color: "#74807b", fontWeight: 500 }}>支持产业分析、招商推荐、风险评估与政策匹配</small></div>
          </div>
          <Button
            type="primary"
            size="large"
            icon={running ? <LoadingOutlined spin /> : <PlayCircleOutlined />}
            onClick={runTask}
            loading={running}
            disabled={running || !input.trim()}
          >
            {running ? "AI 团队执行中" : "启动 AI 运营团队"}
          </Button>
        </div>
        <Input.TextArea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          autoSize={{ minRows: 1, maxRows: 3 }}
          disabled={running}
        />
      </section>

      <div className="workspace-flow">
      <Card
        className="workspace-process"
        size="small"
        title={<><ThunderboltOutlined style={{ color: "#c58a42" }} /> 执行流程</>}
      >
        <Steps
          current={currentPhase}
          size="small"
          status={error ? "error" : currentPhase >= 3 ? "finish" : "process"}
          items={phases.map((phase, index) => ({
            title: phase.title,
            description: phase.description,
            icon: phase.icon,
            status:
              index < currentPhase
                ? "finish"
                : index === currentPhase
                  ? error ? "error" : "process"
                  : "wait",
          }))}
        />
      </Card>

      <Card
        className="workspace-team"
        size="small"
        title={<><TeamOutlined style={{ color: "#4f8f7a" }} /> Agent 执行链</>}
        extra={
          <Badge
            status={running ? "processing" : response ? "success" : error ? "error" : "default"}
            text={running ? `执行中（${completedCount}/6）` : response ? "任务完成" : error ? "执行失败" : "待启动"}
          />
        }
      >
        <div className="workspace-agent-grid">
          {agents.map((agent) => {
            const context = extractContext(input);
            const route = buildAgentRoute(agent.name, context);
            const isClickable = agent.status === "completed";
            const tooltip = getAgentTooltip(agent);
            return (
            <Card
              key={agent.name}
              size="small"
              className="workspace-agent"
              data-status={agent.status}
              data-clickable={isClickable || undefined}
              role={isClickable ? "link" : undefined}
              tabIndex={isClickable ? 0 : undefined}
              styles={{ body: { padding: 10 } }}
              onClick={() => {
                if (!isClickable) return;
                router.push(route.path);
              }}
              onKeyDown={(event) => {
                if (isClickable && (event.key === "Enter" || event.key === " ")) {
                  event.preventDefault();
                  router.push(route.path);
                }
              }}
              title={tooltip}
            >
              <div className="workspace-agent-head">
                <div className="workspace-agent-emoji">{agent.icon}</div>
                <div className="workspace-agent-name"><strong>{agent.display}</strong><span>{agent.role}</span></div>
              </div>
              {agent.status === "running" && <Tag icon={<LoadingOutlined spin />} color="blue">执行中</Tag>}
              {agent.status === "completed" && <Tag icon={<CheckCircleOutlined />} color="green">完成</Tag>}
              {agent.status === "failed" && <Tag icon={<CloseCircleOutlined />} color="red">失败</Tag>}
              {agent.status === "pending" && <Tag>待命</Tag>}
              {agent.action && <div className="workspace-agent-action">{agent.action}</div>}
              {isClickable && (
                <div style={{ fontSize: 10, color: "#2f6f64", marginTop: 4 }}>
                  <NodeIndexOutlined /> {route.label}
                </div>
              )}
            </Card>
          )})}
        </div>
      </Card>
      </div>

      {response ? (
        <>
        <Card
          className="workspace-report"
          size="small"
          style={{ marginBottom: 16 }}
          title={<><BulbOutlined style={{ color: "#c58a42" }} /> AI 产业运营决策报告</>}
          extra={
            <Space>
              <Tag color="green">{usedAgents.length} Agent 参与</Tag>
              <Tag color="blue">{elapsed}s</Tag>
              {taskId && <a href={`/agent/trace/${taskId}`}><NodeIndexOutlined /> 执行链路</a>}
            </Space>
          }
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{response}</ReactMarkdown>
        </Card>

        {investReady && investScenarioId && (
        <Card
          size="small"
          style={{ marginBottom: 16, borderLeft: "4px solid #4f8f7a", background: "#f0f7f3" }}
        >
          <div className="workspace-invest-ready">
            <div>
              <Text strong style={{ fontSize: 14 }}>
                <CheckCircleOutlined style={{ color: "#4f8f7a", marginRight: 6 }} />
                结构化招商结果已自动生成
              </Text>
              <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                招商决策中心已同步创建场景，可直接查看企业评分排名和证据链
              </div>
            </div>
            <Button
              type="primary"
              icon={<SearchOutlined />}
              onClick={() => router.push(`/dashboard/investment?scenario=${investScenarioId}`)}
            >
              立即查看
            </Button>
          </div>
        </Card>
        )}

        <Card
          size="small"
          title={<><RocketOutlined style={{ color: "#2f6f64" }} /> 下一步：进入专业决策看板</>}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            {usedAgents.includes("InvestmentAgent") && (() => {
              const ctx = extractContext(input);
              const investRoute = `/dashboard/investment?industry=${encodeURIComponent(ctx.industry)}&roles=${encodeURIComponent(ctx.roles.join(","))}&location=${encodeURIComponent(ctx.location)}`;
              return (
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={() => router.push(investRoute)}
              >
                招商决策中心
              </Button>
            )})()}
            {usedAgents.includes("RiskAgent") && (
              <Button
                icon={<SafetyCertificateOutlined />}
                onClick={() => router.push("/dashboard/risk")}
              >
                企业风险监测
              </Button>
            )}
            {usedAgents.includes("PolicyAgent") && (
              <Button
                icon={<FileTextOutlined />}
                onClick={() => router.push("/management/policies")}
              >
                惠企政策库
              </Button>
            )}
            {usedAgents.includes("BIAgent") && (
              <Button
                icon={<BarChartOutlined />}
                onClick={() => router.push("/dashboard/bi")}
              >
                经营分析看板
              </Button>
            )}
            <Button
              icon={<DashboardOutlined />}
              onClick={() => router.push("/dashboard")}
            >
              园区运营总览
            </Button>
          </div>
          <div style={{ marginTop: 10 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              点击「招商决策中心」将自动带入本次产业方向和地域偏好并启动寻商；点击上方 Agent 卡片也可直达对应专业页面。
              报告为 AI 生成的自然语言摘要，结构化评分和证据链请在各看板中查看。
            </Text>
          </div>
        </Card>
        </>
      ) : (
        <div className="workspace-empty">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={running ? "等待真实后端返回任务结果…" : "启动任务后在这里显示真实生成报告"}
          />
        </div>
      )}
    </div>
  );
}
