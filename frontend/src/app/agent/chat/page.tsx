"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Input, Button, Card, Tag, Space, Badge, Typography } from "antd";
import {
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  NodeIndexOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import { apiFetch } from "@/api/fetch";

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

const AGENT_DISPLAY: Record<string, { display: string; icon: string }> = {
  Supervisor: { display: "AI运营总经理", icon: "👔" },
  IndustryAgent: { display: "AI产业研究院", icon: "🔬" },
  InvestmentAgent: { display: "AI招商经理", icon: "💼" },
  RiskAgent: { display: "企业风险雷达", icon: "🛡️" },
  PolicyAgent: { display: "AI政策顾问", icon: "📋" },
  EnterpriseServiceAgent: { display: "AI企业管家", icon: "🏢" },
  BIAgent: { display: "AI数字驾驶舱", icon: "📊" },
};

const DEFAULT_AGENTS: AgentStatus[] = [
  { name: "Supervisor", display: "AI运营总经理", icon: "👔", status: "pending", action: "等待任务" },
  { name: "IndustryAgent", display: "AI产业研究院", icon: "🔬", status: "pending", action: "待命中" },
  { name: "InvestmentAgent", display: "AI招商经理", icon: "💼", status: "pending", action: "待命中" },
  { name: "RiskAgent", display: "企业风险雷达", icon: "🛡️", status: "pending", action: "待命中" },
  { name: "PolicyAgent", display: "AI政策顾问", icon: "📋", status: "pending", action: "待命中" },
];

export default function AgentChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [showAgents, setShowAgents] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, agents]);

  useEffect(() => {
    const prompt = new URLSearchParams(window.location.search).get("prompt");
    if (prompt) setInput(prompt);
  }, []);

  const handleSend = useCallback(async () => {
    if (!input.trim() || loading) return;

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

    try {
      const t0 = performance.now();
      const res = await apiFetch(`${API}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query }),
      });
      const data = await res.json();

      // P3: streaming 模式 — 通过 SSE 接收实时事件
      if (data.stream_url) {
        const es = new EventSource(`${API}${data.stream_url}`);

        es.addEventListener("node_complete", (e) => {
          const parsed = JSON.parse(e.data);
          const node = parsed.payload?.node || "";
          if (node === "intent_recognition") {
            setAgents((prev) =>
              prev.map((a) =>
                a.name === "Supervisor"
                  ? { ...a, status: "running" as const, action: "意图识别完成" }
                  : a
              )
            );
          } else if (node === "task_planner") {
            setAgents((prev) =>
              prev.map((a) =>
                a.name === "Supervisor"
                  ? { ...a, status: "completed" as const, action: "✅ 任务规划完成", duration: "0.5s" }
                  : { ...a, status: "running" as const, action: "等待调度" }
              )
            );
          }
        });

        es.addEventListener("agent_start", (e) => {
          const parsed = JSON.parse(e.data);
          const agent = parsed.payload?.agent || "";
          setAgents((prev) =>
            prev.map((a) =>
              a.name === agent
                ? { ...a, status: "running" as const, action: "执行中..." }
                : a
            )
          );
        });

        es.addEventListener("agent_done", (e) => {
          const parsed = JSON.parse(e.data);
          const agent = parsed.payload?.agent || "";
          const summary = parsed.payload?.summary || "";
          const ms = parsed.payload?.execution_time_ms || 0;
          setAgents((prev) =>
            prev.map((a) =>
              a.name === agent
                ? {
                    ...a,
                    status: "completed" as const,
                    action: summary.slice(0, 50) || "✅ 完成",
                    duration: `${(ms / 1000).toFixed(1)}s`,
                  }
                : a
            )
          );
        });

        es.addEventListener("agent_error", (e) => {
          const parsed = JSON.parse(e.data);
          const agent = parsed.payload?.agent || "";
          setAgents((prev) =>
            prev.map((a) =>
              a.name === agent
                ? { ...a, status: "failed" as const, action: "❌ 执行失败" }
                : a
            )
          );
        });

        es.addEventListener("done", (e) => {
          const parsed = JSON.parse(e.data);
          const finalResp = parsed.payload?.final_response || "";
          const usedAgents: string[] = parsed.payload?.agents_used || [];
          const tId = parsed.payload?.task_id || data.task_id;

          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: finalResp,
              agents: usedAgents,
              taskId: tId,
            },
          ]);
          setLoading(false);
          es.close();
        });

        es.onerror = () => {
          setLoading(false);
          es.close();
        };
        return;
      }

      // === v1.2 兼容: 同步模式 (streaming disabled) ===
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
        content: data.response || "处理完成",
        agents: usedAgents,
        traceId: data.trace_id,
        taskId: data.task_id,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "抱歉，服务暂不可用" },
      ]);
      setAgents(DEFAULT_AGENTS);
    } finally {
      if (loading) setLoading(false);
    }
  }, [input, loading]);

  return (
    <div style={{ display: "flex", height: "calc(100vh - 200px)", gap: 0 }}>
      {/* Left: Chat area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
          {messages.length === 0 && (
            <div style={{ textAlign: "center", marginTop: 60, color: "#999" }}>
              <RobotOutlined style={{ fontSize: 56, color: "#1677ff" }} />
              <h2 style={{ marginTop: 16 }}>AI 产业运营官</h2>
              <p style={{ fontSize: 15 }}>
                试试输入：帮广州打造机器人产业园，寻找产业链企业并制定招商方案
              </p>
              <div style={{ marginTop: 16 }}>
                {["🔍 产业分析", "💼 招商推荐", "🛡️ 风险评估", "📋 政策匹配"].map(
                  (s, i) => (
                    <Tag
                      key={i}
                      style={{ cursor: "pointer", margin: 4, fontSize: 13, padding: "2px 10px" }}
                      onClick={() => {
                        const texts = [
                          "分析广州机器人产业链缺口",
                          "推荐广州机器人产业招商目标企业",
                          "评估广州机器人产业投资风险",
                          "查找广州机器人产业相关政策支持",
                        ];
                        setInput(texts[i]);
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
              key={i}
              size="small"
              style={{
                marginBottom: 12,
                maxWidth: "85%",
                marginLeft: msg.role === "user" ? "auto" : 0,
                background: msg.role === "user" ? "#e6f7ff" : "#fff",
                border: msg.role === "assistant" ? "1px solid #d9d9d9" : undefined,
              }}
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
                </div>
              </Space>
            </Card>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div
          style={{
            display: "flex",
            gap: 8,
            padding: "12px 24px",
            borderTop: "1px solid #f0f0f0",
            background: "#fafafa",
          }}
        >
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="输入招商/政策/风险/产业分析需求... (Enter 发送, Shift+Enter 换行)"
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
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: loading ? 8 : 0 }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>
              <ThunderboltOutlined style={{ color: "#1677ff", marginRight: 6 }} />
              Agent 协作面板
            </span>
            <Badge
              status={loading ? "processing" : "success"}
              text={loading ? "执行中" : "就绪"}
            />
          </div>
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
            return (
              <div
                key={a.name}
                style={{
                  padding: "10px 12px",
                  marginBottom: 8,
                  borderRadius: 8,
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
                  transition: "all 0.3s",
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
