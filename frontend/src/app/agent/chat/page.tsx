"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Input, Button, Card, Tag, Space, Badge, Typography, Popconfirm } from "antd";
import {
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  NodeIndexOutlined,
  BulbOutlined,
  SearchOutlined,
  SafetyOutlined,
  FileTextOutlined,
  DashboardOutlined,
  TeamOutlined,
  DeleteOutlined,
  ClearOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiJson, resolveApiUrl } from "@/api/fetch";
import { useDataMode } from "@/contexts/DataModeContext";

const { Text } = Typography;

const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface Message {
  role: "user" | "assistant";
  content: string;
  agents?: string[];
  traceId?: string;
  taskId?: string;
}

interface AgentStatus {
  name: string;
  display: string;
  icon: string;
  status: "pending" | "running" | "completed" | "failed";
  action?: string;
  duration?: string;
}

interface ChatStartResponse {
  task_id: string;
  conversation_id?: string;
  status: string;
  response?: string | null;
  stream_url?: string | null;
  agents_used?: string[];
  trace_id?: string;
}

const AGENT_DISPLAY: Record<string, { display: string; icon: string }> = {
  Supervisor: { display: "AI运营总经理", icon: "👔" },
  IndustryAgent: { display: "AI产业研究院", icon: "🔬" },
  InvestmentAgent: { display: "AI招商经理", icon: "💼" },
  RiskAgent: { display: "企业风险雷达", icon: "🛡️" },
  PolicyAgent: { display: "AI政策顾问", icon: "📋" },
  EnterpriseServiceAgent: { display: "AI企业服务助手", icon: "🏢" },
  BIAgent: { display: "AI经营分析师", icon: "📊" },
};

const AGENT_ROUTES: Record<string, { path: string; label: string }> = {
  Supervisor:        { path: "/agent/team",                       label: "智能体团队" },
  IndustryAgent:     { path: "/agent/chat",                       label: "产业分析" },
  InvestmentAgent:   { path: "/dashboard/investment",             label: "招商决策中心" },
  RiskAgent:         { path: "/dashboard/risk",                   label: "风险看板" },
  PolicyAgent:       { path: "/management/policies",              label: "惠企政策库" },
  BIAgent:           { path: "/dashboard/bi",                     label: "经营分析看板" },
  EnterpriseServiceAgent: { path: "/agent/chat",                 label: "企业服务咨询" },
};

const FOLLOW_UP_SUGGESTIONS: Record<string, string[]> = {
  IndustryAgent: [
    "这个产业链的上游还有哪些关键环节？",
    "对比一下广州和深圳在该产业的优势差异",
    "近两年该产业的政策支持力度如何？",
  ],
  InvestmentAgent: [
    "帮我详细分析排名第一的企业",
    "这些企业的技术能力证据在哪里？",
    "有没有更适合初创企业对接的选择？",
  ],
  RiskAgent: [
    "高风险企业的具体风险原因是什么？",
    "有没有供应链相关的风险案例？",
    "如何评估一家新入园企业的风险？",
  ],
  PolicyAgent: [
    "有没有针对中小企业的税收优惠政策？",
    "最近的产业扶持项目申报条件是什么？",
    "人才引进相关的补贴政策有哪些？",
  ],
  BIAgent: [
    "园区的招商转化率趋势如何？",
    "本月AI任务的完成情况怎么样？",
    "和上个月比园区运营指标有什么变化？",
  ],
  EnterpriseServiceAgent: [
    "办理这类事项还需要补充哪些信息？",
    "这个诉求应该由园区哪个岗位受理？",
    "请整理一份人工登记清单",
  ],
  default: [
    "能再详细一些吗？",
    "有没有具体的数据支持这个结论？",
    "这个建议的下一步应该怎么做？",
  ],
};

function getFollowUps(agentsUsed: string[]): string[] {
  const suggestions: string[] = [];
  for (const agent of agentsUsed) {
    const sugs = FOLLOW_UP_SUGGESTIONS[agent];
    if (sugs) suggestions.push(sugs[0]);
  }
  if (suggestions.length === 0) suggestions.push(...FOLLOW_UP_SUGGESTIONS.default);
  return suggestions.slice(0, 3);
}

const DEFAULT_AGENTS: AgentStatus[] = [
  { name: "Supervisor", display: "AI运营总经理", icon: "👔", status: "pending", action: "等待任务" },
  { name: "IndustryAgent", display: "AI产业研究院", icon: "🔬", status: "pending", action: "待命中" },
  { name: "InvestmentAgent", display: "AI招商经理", icon: "💼", status: "pending", action: "待命中" },
  { name: "RiskAgent", display: "企业风险雷达", icon: "🛡️", status: "pending", action: "待命中" },
  { name: "PolicyAgent", display: "AI政策顾问", icon: "📋", status: "pending", action: "待命中" },
  { name: "EnterpriseServiceAgent", display: "AI企业服务助手", icon: "🏢", status: "pending", action: "待命中" },
  { name: "BIAgent", display: "AI经营分析师", icon: "📊", status: "pending", action: "待命中" },
];

export default function AgentChatPage() {
  const router = useRouter();
  const { mode, isDemo } = useDataMode();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [showAgents, setShowAgents] = useState(true);
  const [hydrated, setHydrated] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Persist chat history to sessionStorage so it survives navigation
  const STORAGE_KEY = "chat_last_session";
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.messages?.length) setMessages(parsed.messages);
        if (parsed.agents?.length) setAgents(parsed.agents);
        if (parsed.input) setInput(parsed.input);
      }
    } catch { /* ignore */ }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (messages.length > 0 && !loading) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ messages, agents, input }));
    }
  }, [messages, loading, hydrated]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, agents]);

  useEffect(() => {
    const prompt = new URLSearchParams(window.location.search).get("prompt");
    if (prompt) setInput(prompt);
  }, []);

  const handleSend = useCallback(async () => {
    if (!input.trim() || loading) return;

    sessionStorage.removeItem(STORAGE_KEY);
    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    const query = input;
    setInput("");
    setLoading(true);

    // P3: 重置 Agent 面板为初始状态
    setAgents(
      DEFAULT_AGENTS.map((a) => ({
        ...a,
        status: "pending" as const,
        action: a.name === "Supervisor" ? "分析中..." : "等待调度",
      }))
    );

    let streamingStarted = false;
    try {
      const t0 = performance.now();
      const data = await apiJson<ChatStartResponse>(`${API}/agent/chat`, {
        method: "POST",
        body: JSON.stringify({
          message: query,
          context: { data_mode: mode },
          history: messages.slice(-6).map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (data.stream_url) {
        streamingStarted = true;
        let terminal = false;
        const es = new EventSource(resolveApiUrl(data.stream_url, API));

        es.addEventListener("snapshot", (event) => {
          const snapshot = JSON.parse((event as MessageEvent).data);
          const results = snapshot.agent_results || {};
          setAgents((prev) =>
            prev.map((agent) => {
              if (agent.name === "Supervisor") {
                return { ...agent, status: "running", action: "正在编排任务..." };
              }
              const result = results[agent.name];
              if (!result) return agent;
              return {
                ...agent,
                status: result.status === "failed" ? "failed" : "completed",
                action: result.summary || (result.status === "failed" ? "执行失败" : "已完成"),
                duration: result.execution_time_ms
                  ? `${(result.execution_time_ms / 1000).toFixed(1)}s`
                  : undefined,
              };
            }),
          );
        });

        es.addEventListener("done", (event) => {
          terminal = true;
          const parsed = JSON.parse((event as MessageEvent).data);
          const payload = parsed.payload || {};
          const usedAgents: string[] = payload.agents_used || [];
          setAgents((prev) =>
            prev.map((agent) => ({
              ...agent,
              status:
                agent.name === "Supervisor" || usedAgents.includes(agent.name)
                  ? "completed"
                  : "pending",
              action:
                agent.name === "Supervisor"
                  ? `调度 ${usedAgents.length} 个 Agent 完成`
                  : usedAgents.includes(agent.name)
                    ? "已参与本次任务"
                    : "本次未调用",
            })),
          );
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: payload.final_response || "任务已完成，但后端未返回报告内容。",
              agents: usedAgents,
              traceId: payload.trace_id,
              taskId: payload.task_id || data.task_id,
            },
          ]);
          setLoading(false);
          es.close();
        });

        es.addEventListener("error", (event) => {
          if (terminal || !(event instanceof MessageEvent)) return;
          terminal = true;
          const parsed = JSON.parse(event.data);
          const message = parsed.payload?.message || "Agent 执行失败";
          setMessages((prev) => [...prev, { role: "assistant", content: `执行失败：${message}` }]);
          setAgents((prev) =>
            prev.map((agent) =>
              agent.name === "Supervisor"
                ? { ...agent, status: "failed", action: message }
                : agent,
            ),
          );
          setLoading(false);
          es.close();
        });

        es.onerror = () => {
          if (terminal) return;
          terminal = true;
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: "实时连接中断，请重新发送或稍后重试。" },
          ]);
          setAgents((prev) =>
            prev.map((agent) =>
              agent.name === "Supervisor"
                ? { ...agent, status: "failed", action: "实时连接中断" }
                : agent,
            ),
          );
          setLoading(false);
          es.close();
        };
        return;
      }

      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      const usedAgents: string[] = data.agents_used || [];

      setAgents((prev) =>
        prev.map((a) => {
          if (a.name === "Supervisor") {
            return {
              ...a,
              status: "completed" as const,
              action: `✅ 调度 ${usedAgents.length} Agent`,
              duration: "0.5s",
            };
          }
          const wasUsed = usedAgents.includes(a.name);
          return {
            ...a,
            status: wasUsed ? ("completed" as const) : ("pending" as const),
            action: wasUsed ? "✅ 已参与" : "本次未调用",
            duration: wasUsed ? "~2s" : undefined,
          };
        })
      );

      const aiMsg: Message = {
        role: "assistant",
        content: data.response || "任务已完成，但后端未返回报告内容。",
        agents: usedAgents,
        traceId: data.trace_id,
        taskId: data.task_id,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "未知错误";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `请求失败：${message}` },
      ]);
      setAgents(DEFAULT_AGENTS);
    } finally {
      if (!streamingStarted) setLoading(false);
    }
  }, [input, loading, mode]);

  return (
    <div className="chat-layout">
      {/* Left: Chat area */}
      <div className="chat-main">
        <div className="chat-messages" aria-live="polite">
          {messages.length === 0 && (
            <div style={{ textAlign: "center", marginTop: 60, color: "#999" }}>
              <RobotOutlined style={{ fontSize: 56, color: "#1677ff" }} />
              <h2 style={{ marginTop: 16 }}>AI 园区运营助手</h2>
              <Tag color={isDemo ? "orange" : "blue"}>
                {isDemo ? "演示沙盘 · 仅使用固定合成场景" : "公开快照 · 缺失数据不推测"}
              </Tag>
              <p style={{ fontSize: 15 }}>
                试试输入：帮广州打造机器人产业园，寻找产业链企业并制定招商方案
              </p>
              <div style={{ marginTop: 16 }}>
                {["🔍 产业分析", "💼 招商推荐", "🛡️ 风险评估", "📋 政策匹配", "🏢 企业服务", "📊 经营分析"].map(
                  (s, i) => (
                    <Tag
                      key={i}
                      role="button"
                      tabIndex={0}
                      style={{ cursor: "pointer", margin: 4, fontSize: 13, padding: "2px 10px" }}
                      onClick={() => {
                        const texts = [
                          "分析广州机器人产业链缺口",
                          "推荐广州机器人产业招商目标企业",
                          "评估广州机器人产业投资风险",
                          "查找广州机器人产业相关政策支持",
                          "园区企业有一项物业诉求，请给出人工办理清单",
                          "汇总园区经营指标和招商漏斗",
                        ];
                        setInput(texts[i]);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          const texts = [
                            "分析广州机器人产业链缺口",
                            "推荐广州机器人产业招商目标企业",
                            "评估广州机器人产业投资风险",
                            "查找广州机器人产业相关政策支持",
                            "园区企业有一项物业诉求，请给出人工办理清单",
                            "汇总园区经营指标和招商漏斗",
                          ];
                          setInput(texts[i]);
                        }
                      }}
                    >
                      {s}
                    </Tag>
                  )
                )}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <Card
              className="chat-message"
              key={i}
              size="small"
              style={{
                marginBottom: 12,
                maxWidth: "85%",
                marginLeft: msg.role === "user" ? "auto" : 0,
                background: msg.role === "user" ? "#e6f7ff" : "#fff",
                border: msg.role === "assistant" ? "1px solid #d9d9d9" : undefined,
                position: "relative",
              }}
              extra={
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  aria-label="删除这条消息"
                  onClick={() => {
                    setMessages((prev) => prev.filter((_, idx) => idx !== i));
                  }}
                  className="message-delete"
                />
              }
            >
              <Space align="start">
                {msg.role === "user" ? (
                  <UserOutlined style={{ marginTop: 4 }} />
                ) : (
                  <RobotOutlined style={{ color: "#1677ff", marginTop: 4 }} />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  {msg.agents && msg.agents.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, marginRight: 6 }}>
                        <NodeIndexOutlined /> 调用 Agent:
                      </Text>
                      {msg.agents.map((a) => {
                        const info = AGENT_DISPLAY[a] || { display: a, icon: "🤖" };
                        return (
                          <Tag key={a} color="blue" style={{ marginBottom: 4 }}>
                            {info.icon} {info.display}
                          </Tag>
                        );
                      })}
                    </div>
                  )}
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h2: ({ children }) => (
                        <h3 style={{ borderBottom: "1px solid #f0f0f0", paddingBottom: 6 }}>
                          {children}
                        </h3>
                      ),
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                  {msg.taskId && (
                    <a
                      href={`/agent/trace/${msg.taskId}`}
                      style={{ fontSize: 12, color: "#1677ff", marginTop: 8, display: "inline-block" }}
                    >
                      <NodeIndexOutlined /> 查看 Agent 执行链路 →
                    </a>
                  )}
                  {msg.role === "assistant" && msg.agents && msg.agents.length > 0 && (
                    <div style={{ marginTop: 10, borderTop: "1px dashed #f0f0f0", paddingTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 6 }}>
                        <BulbOutlined /> 继续追问：
                      </Text>
                      <Space wrap size={[4, 4]}>
                        {getFollowUps(msg.agents).map((suggestion, idx) => (
                          <Tag
                            key={idx}
                            color="blue"
                            role="button"
                            tabIndex={0}
                            style={{ cursor: "pointer", fontSize: 12 }}
                            onClick={() => { setInput(suggestion); }}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                setInput(suggestion);
                              }
                            }}
                          >
                            {suggestion}
                          </Tag>
                        ))}
                      </Space>
                    </div>
                  )}
                </div>
              </Space>
            </Card>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="chat-composer">
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="输入产业、招商、风险、政策、经营指标或企业服务需求... (Enter 发送, Shift+Enter 换行)"
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
            style={{ fontSize: 14 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            size="large"
          >
            发送
          </Button>
        </div>
      </div>

      {/* Right: Multi-Agent Collaboration Panel */}
      <div
        className="chat-agent-panel"
        style={{
          width: 280,
          borderLeft: "1px solid #f0f0f0",
          background: "#fafafa",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "12px 16px",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>
              <ThunderboltOutlined style={{ color: "#1677ff", marginRight: 6 }} />
              Agent 协作面板
            </span>
            <Badge
              status={loading ? "processing" : "success"}
              text={loading ? "执行中" : "就绪"}
            />
          </div>
          {messages.length > 0 && !loading && (
            <Popconfirm
              title="清空全部对话？"
              description="当前会话内容将从本机浏览器中移除。"
              okText="确认清空"
              cancelText="取消"
              onConfirm={() => {
                setMessages([]);
                setAgents([]);
                setInput("");
                sessionStorage.removeItem(STORAGE_KEY);
              }}
            >
              <Button size="small" danger icon={<ClearOutlined />} style={{ fontSize: 11, width: "100%", marginTop: 6 }}>
                清空全部对话
              </Button>
            </Popconfirm>
          )}
          {loading && (
            <div style={{ marginTop: 4 }}>
              <div style={{ fontSize: 11, color: "#999", marginBottom: 2 }}>
                任务进度: {agents.filter((a) => a.status === "completed" || a.status === "running").length}/{agents.length} Agent
              </div>
              <div style={{ height: 4, background: "#f0f0f0", borderRadius: 2, overflow: "hidden" }}>
                <div style={{
                  height: "100%", background: "linear-gradient(90deg, #1677ff, #52c41a)",
                  width: `${(agents.filter((a) => a.status === "completed" || a.status === "running").length / agents.length) * 100}%`,
                  transition: "width 0.5s",
                  borderRadius: 2,
                }} />
              </div>
            </div>
          )}
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: 12 }}>
          {(agents.length > 0 ? agents : DEFAULT_AGENTS).map((a) => {
            const isRunning = a.status === "running";
            const isCompleted = a.status === "completed";
            const isFailed = a.status === "failed";
            const route = AGENT_ROUTES[a.name];
            const clickable = isCompleted && !!route;
            return (
              <div
                key={a.name}
                onClick={() => { if (clickable) router.push(route.path); }}
                onKeyDown={(event) => {
                  if (clickable && (event.key === "Enter" || event.key === " ")) {
                    event.preventDefault();
                    router.push(route.path);
                  }
                }}
                role={clickable ? "link" : undefined}
                tabIndex={clickable ? 0 : undefined}
                title={clickable ? `点击跳转：${route.label}` : ""}
                style={{
                  padding: "10px 12px",
                  marginBottom: 8,
                  borderRadius: 8,
                  cursor: clickable ? "pointer" : "default",
                  background: isRunning
                    ? "#e6f7ff"
                    : isCompleted
                    ? "#f6ffed"
                    : isFailed
                    ? "#fff2f0"
                    : "#fff",
                  border: `1px solid ${
                    isRunning ? "#91caff" : isCompleted ? "#b7eb8f" : isFailed ? "#ffccc7" : "#f0f0f0"
                  }`,
                  transition: "all 0.2s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 18 }}>{a.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{a.display}</div>
                    <div style={{ fontSize: 11, color: "#999" }}>{a.name}</div>
                  </div>
                  <span>
                    {isRunning ? (
                      <LoadingOutlined style={{ color: "#1677ff" }} spin />
                    ) : isCompleted ? (
                      <CheckCircleOutlined style={{ color: "#52c41a" }} />
                    ) : isFailed ? (
                      <ClockCircleOutlined style={{ color: "#ff4d4f" }} />
                    ) : (
                      <ClockCircleOutlined style={{ color: "#d9d9d9" }} />
                    )}
                  </span>
                </div>
                {a.action && (
                  <div
                    style={{
                      fontSize: 11,
                      color: isCompleted ? "#52c41a" : isFailed ? "#ff4d4f" : isRunning ? "#1677ff" : "#999",
                      marginTop: 4,
                      paddingLeft: 26,
                    }}
                  >
                    {a.action}
                    {a.duration && (
                      <span style={{ marginLeft: 8, color: "#999" }}>{a.duration}</span>
                    )}
                  </div>
                )}
                {clickable && (
                  <div style={{ fontSize: 10, color: "#1677ff", marginTop: 4, paddingLeft: 26 }}>
                    <NodeIndexOutlined /> {route.label}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Summary footer */}
        {!loading && agents.some((a) => a.status === "completed") && (
          <div
            style={{
              padding: "10px 16px",
              borderTop: "1px solid #f0f0f0",
              fontSize: 12,
              background: "#f6ffed",
            }}
          >
            <div style={{ color: "#52c41a", marginBottom: 4, textAlign: "center" }}>
              <CheckCircleOutlined style={{ marginRight: 4 }} />
              {agents.filter((a) => a.status === "completed").length} Agent 协作完成
            </div>
            <div style={{ fontSize: 10, color: "#999", textAlign: "center" }}>
              调用链: Supervisor → {agents.filter((a) => a.status === "completed" && a.name !== "Supervisor").map((a) => a.display).join(" → ") || "等待"}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
