"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Progress,
  Row,
  Select,
  Slider,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import {
  AuditOutlined,
  CheckCircleOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  addCandidate,
  createScenario,
  downloadScenarioPdf,
  getOfflineLearningReport,
  getLatestEvaluation,
  getRecommendations,
  recordRecommendationExposure,
  type ScenarioInput,
} from "@/api/investment.api";
import CandidatePool from "@/components/investment/CandidatePool";
import EvidenceDrawer from "@/components/investment/EvidenceDrawer";
import styles from "@/components/investment/investment.module.css";
import PageHeader from "@/components/layout/PageHeader";
import { useDataMode } from "@/contexts/DataModeContext";
import { useUserContext } from "@/contexts/UserContext";
import type {
  InvestmentEvaluationReport,
  OfflineLearningReport,
  PolicyMatch,
  RecommendationCard,
  RecommendationResponse,
} from "@/types/investment";

const { Paragraph, Text, Title } = Typography;

const DIMENSION_LABELS: Record<string, string> = {
  industry_fit: "产业匹配度",
  technology: "技术能力",
  growth: "成长潜力",
  landing_intent: "落地意愿",
  policy_fit: "政策适配度",
  data_completeness: "数据完整度",
};

const DEFAULT_WEIGHT_PERCENT: Record<string, number> = {
  industry_fit: 30,
  technology: 20,
  growth: 15,
  landing_intent: 10,
  policy_fit: 15,
  data_completeness: 10,
};

const UNKNOWN_LABELS: Record<string, string> = {
  growth: "成长数据",
  landing_intent: "落地意愿",
  policy_fit: "政策申报条件",
  risk: "真实风险评估",
};

const RISK_COLOR = {
  HIGH: "red",
  MEDIUM: "orange",
  LOW: "green",
  UNKNOWN: "default",
} as const;

const RISK_LABEL = {
  HIGH: "高风险",
  MEDIUM: "中风险",
  LOW: "低风险",
  UNKNOWN: "待核验",
} as const;

const SCENARIO_PRESETS: Array<{
  label: string;
  values: Pick<ScenarioInput, "target_chain_roles" | "location_preference" | "limit">;
}> = [
  {
    label: "全链条扫描",
    values: {
      target_chain_roles: ["核心零部件", "系统集成", "工业软件"],
      location_preference: "广州",
      limit: 5,
    },
  },
  {
    label: "核心零部件",
    values: {
      target_chain_roles: ["核心零部件", "伺服与驱动", "机器视觉"],
      location_preference: "粤港澳大湾区",
      limit: 5,
    },
  },
  {
    label: "工业软件",
    values: {
      target_chain_roles: ["工业软件", "系统集成"],
      location_preference: "广州",
      limit: 5,
    },
  },
];

function RecommendationRanking({
  recommendations,
  selectedId,
  onSelect,
}: {
  recommendations: RecommendationCard[];
  selectedId?: string;
  onSelect: (item: RecommendationCard) => void;
}) {
  return (
    <section className={styles.rankingPanel} aria-label="企业推荐排名">
      <div className={styles.panelHeader}>
        <Text className={styles.sectionKicker}>优先级队列</Text>
        <Title level={5} className={styles.sectionTitle}>
          候选企业
        </Title>
        <Text type="secondary">证据充分时按推荐分排序；证据不足时按数据置信度展示线索</Text>
      </div>
      <div className={styles.rankingList}>
        {recommendations.map((item, index) => {
          const active = item.enterprise_id === selectedId;
          return (
            <button
              key={item.enterprise_id}
              type="button"
              className={`${styles.rankingItem} ${
                active ? styles.rankingItemSelected : ""
              }`}
              aria-pressed={active}
              onClick={() => onSelect(item)}
            >
              <span className={styles.rankNumber}>{index + 1}</span>
              <span>
                <span className={styles.rankName}>{item.enterprise_name}</span>
                <span className={styles.rankMeta}>
                  <span>{item.industry_chain_role || "产业链角色待判定"}</span>
                  <span>·</span>
                  <span>置信度 {Math.round((item.confidence || 0) * 100)}%</span>
                  <span>·</span>
                  <span>{item.evidence.length} 条证据</span>
                </span>
              </span>
              <span>
                <span className={styles.rankScore}>
                  {item.overall_score == null ? "待补证" : item.overall_score.toFixed(1)}
                </span>
                <span className={styles.rankScoreUnit}>{item.overall_score == null ? "暂不评分" : "推荐分"}</span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

const AGENT_LABELS: Record<string, string> = {
  Supervisor: "Supervisor 编排",
  IndustryAgent: "产业链研判",
  InvestmentAgent: "企业召回",
  EnterpriseData: "企业数据补全",
  RiskAgent: "真实风险核验",
  PolicyAgent: "政策资格核验",
};

const AGENT_STATUS_LABELS = {
  SUCCESS: "已完成",
  DATA_INSUFFICIENT: "证据不足",
  FAILED: "执行失败",
} as const;

const AGENT_STATUS_COLORS = {
  SUCCESS: "success",
  DATA_INSUFFICIENT: "warning",
  FAILED: "error",
} as const;

const POLICY_STATUS_LABELS = {
  ELIGIBLE: "符合条件",
  POTENTIALLY_ELIGIBLE: "可能符合",
  INELIGIBLE: "不符合",
  RELATED: "仅政策相关",
  UNKNOWN: "待核验",
} as const;

const CONDITION_STATUS_LABELS = {
  SATISFIED: "满足",
  UNSATISFIED: "不满足",
  UNKNOWN: "证据不足",
  NEEDS_MANUAL_REVIEW: "人工复核",
  NOT_APPLICABLE: "不适用",
} as const;

const POLICY_PREVIEW_LIMIT = 3;

function PolicyMatchCard({ policy }: { policy: PolicyMatch }) {
  const matchedTerms = policy.matched_terms || [];
  const isParkMaterial = policy.source_type === "park_private_document";

  return (
    <div
      className={styles.policyCard}
      key={`${policy.policy_id || policy.title}-${policy.match_type}`}
    >
      <div className={styles.policyHeader}>
        <div>
          <strong>{policy.title}</strong>
          <p>{policy.reason}</p>
          <div className={styles.policyMeta}>
            {policy.match_score != null && (
              <span>检索相关度 {Math.round(policy.match_score)}%</span>
            )}
            {matchedTerms.length > 0 && (
              <span>命中词：{matchedTerms.join("、")}</span>
            )}
            {policy.source_url && (
              <a href={policy.source_url} target="_blank" rel="noreferrer">
                查看政策原文
              </a>
            )}
          </div>
        </div>
        <Space wrap size={[4, 4]}>
          <Tag color={isParkMaterial ? "cyan" : "blue"}>
            {isParkMaterial ? "园区资料" : "政府政策"}
          </Tag>
          <Tag
            color={
              policy.match_type === "ELIGIBLE"
                ? "success"
                : policy.match_type === "INELIGIBLE"
                  ? "error"
                  : "warning"
            }
          >
            {POLICY_STATUS_LABELS[policy.match_type]}
          </Tag>
        </Space>
      </div>
      {policy.condition_results.length === 0 ? (
        <Text type="secondary">
          仅完成政策相关性检索，尚未配置已复核的申报条件。
        </Text>
      ) : (
        <details className={styles.policyConditions}>
          <summary className={styles.policyConditionsSummary}>
            查看 {policy.condition_results.length} 项申报条件核验
          </summary>
          <div className={styles.conditionList}>
            {policy.condition_results.map((condition) => (
              <div className={styles.conditionRow} key={condition.condition_code}>
                <Tag
                  color={
                    condition.status === "SATISFIED"
                      ? "success"
                      : condition.status === "UNSATISFIED"
                        ? "error"
                        : "warning"
                  }
                >
                  {CONDITION_STATUS_LABELS[condition.status]}
                </Tag>
                <span>
                  <strong>{condition.label || condition.field}</strong>{" "}
                  {condition.operator}{" "}
                  {String(condition.expected_value ?? "—")}
                </span>
                <span className={styles.conditionReason}>{condition.reason}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function AgentVerificationPanel({ item }: { item: RecommendationCard }) {
  const agentOutputs = Object.entries(item.agent_outputs || {});
  const previewPolicies = item.policy_matches.slice(0, POLICY_PREVIEW_LIMIT);
  const remainingPolicies = item.policy_matches.slice(POLICY_PREVIEW_LIMIT);

  return (
    <div className={styles.verificationSection}>
      <div className={styles.sectionHeader}>
        <div>
          <Text className={styles.sectionKicker}>企业级原始输出</Text>
          <Title level={5} className={styles.sectionTitle}>
            Supervisor 与 Agent 核验链
          </Title>
        </div>
        <Text type="secondary">每张决策卡独立保存，可追溯到本次运行</Text>
      </div>

      <div className={styles.agentGrid}>
        {agentOutputs.map(([name, output]) => (
          <details className={styles.agentCard} key={name}>
            <summary className={styles.agentSummary}>
              <span>
                <strong>{AGENT_LABELS[name] || name}</strong>
                <small>{output.evidence_ids.length} 条证据</small>
              </span>
              <Tag color={AGENT_STATUS_COLORS[output.status]}>
                {AGENT_STATUS_LABELS[output.status]}
              </Tag>
            </summary>
            <div className={styles.agentBody}>
              {output.run_ref && (
                <Text type="secondary" copyable>
                  {output.run_ref}
                </Text>
              )}
              {output.unknown_fields.length > 0 && (
                <p>待补字段：{output.unknown_fields.join("、")}</p>
              )}
              {output.warnings.map((warning) => (
                <p className={styles.agentWarning} key={warning}>
                  {warning}
                </p>
              ))}
              <pre className={styles.agentJson}>
                {JSON.stringify(output.result, null, 2)}
              </pre>
            </div>
          </details>
        ))}
      </div>

      <div className={styles.policyList}>
        <div className={styles.sectionHeader}>
          <div>
            <Text className={styles.sectionKicker}>逐企业、逐条件</Text>
            <Title level={5} className={styles.sectionTitle}>
              政策申报资格核验
            </Title>
          </div>
          <Text type="secondary">只展示当前企业的高相关候选，不铺开完整政策库</Text>
        </div>
        <Alert
          className={styles.policyScope}
          type="info"
          showIcon
          message={
            item.policy_matches.length
              ? `当前检索返回 ${item.policy_matches.length} 条政策/园区资料候选，默认展示前 ${Math.min(POLICY_PREVIEW_LIMIT, item.policy_matches.length)} 条`
              : "当前未返回候选政策"
          }
          description={
            <span>
              按产业方向、产业链环节和所在地检索并按相关度排序，不是完整政策清单；未出现不代表不适用。
              {" "}<a href="/management/policies">进入惠企政策库查看全部政策</a>
            </span>
          }
        />
        {item.policy_matches.length === 0 ? (
          <Alert
            type="warning"
            showIcon
            message="尚无可核验的政策条件"
            description="当前企业没有匹配到带已复核结构化条件的政策，政策适配度保持为空。"
          />
        ) : (
          <>
            {previewPolicies.map((policy) => (
              <PolicyMatchCard
                key={`${policy.policy_id || policy.title}-${policy.match_type}`}
                policy={policy}
              />
            ))}
            {remainingPolicies.length > 0 && (
              <details className={styles.morePolicies}>
                <summary className={styles.morePoliciesSummary}>
                  查看其余 {remainingPolicies.length} 条政策/资料候选
                </summary>
                {remainingPolicies.map((policy) => (
                  <PolicyMatchCard
                    key={`${policy.policy_id || policy.title}-${policy.match_type}`}
                    policy={policy}
                  />
                ))}
              </details>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function RecommendationDetail({
  item,
  canWrite,
  added,
  adding,
  onEvidence,
  onAdd,
}: {
  item: RecommendationCard;
  canWrite: boolean;
  added: boolean;
  adding: boolean;
  onEvidence: () => void;
  onAdd: () => void;
}) {
  const unknownItems = item.unknown_fields.map((field) => UNKNOWN_LABELS[field] || field);
  const unknownText = unknownItems.length
    ? unknownItems.join("、")
    : "暂无";
  const unknownSummary = unknownItems.length > 4
    ? `${unknownItems.slice(0, 4).join("、")} 等 ${unknownItems.length} 项`
    : unknownText;
  const publicPolicyCount = item.policy_matches.filter(
    (policy) => policy.source_type !== "park_private_document",
  ).length;
  const parkMaterialCount = item.policy_matches.length - publicPolicyCount;
  const policyCountText = [
    publicPolicyCount ? `${publicPolicyCount} 条政府政策` : "",
    parkMaterialCount ? `${parkMaterialCount} 条园区资料` : "",
  ].filter(Boolean).join("、");

  return (
    <section className={styles.detailPanel} aria-label={`${item.enterprise_name}决策详情`}>
      <div className={styles.detailHeader}>
        <div>
          <Space wrap size={[6, 6]}>
            <Tag color="blue">{item.industry_chain_role || "产业链角色待判定"}</Tag>
            <Tag color={RISK_COLOR[item.risk.level]}>
              {RISK_LABEL[item.risk.level]}
            </Tag>
            {item.data_mode === "demo" && <Tag color="orange">演示沙盘</Tag>}
            {item.data_status === "DATA_INSUFFICIENT" && (
              <Tag color="gold">证据不足</Tag>
            )}
          </Space>
          <Title level={3} className={styles.detailTitle}>
            {item.enterprise_name}
          </Title>
          <Text type="secondary">
            数据置信度 {Math.round((item.confidence || 0) * 100)}% ·{" "}
            {item.evidence.length} 条可追溯证据
          </Text>
        </div>
        <div className={styles.scoreOrb} aria-label={`推荐分 ${item.overall_score ?? "暂无"}`}>
          <span className={styles.scoreOrbValue}>
            {item.overall_score == null ? "—" : item.overall_score.toFixed(1)}
          </span>
          <span className={styles.scoreOrbLabel}>{item.overall_score == null ? "证据不足" : "推荐分"}</span>
        </div>
      </div>

      <div className={styles.detailBody}>
        <div className={styles.decisionBanner}>
          <Text strong>{item.recommendation}</Text>
          <Paragraph type="secondary" style={{ margin: "5px 0 0" }}>
            下一步：{item.next_action}
          </Paragraph>
        </div>

        <div className={styles.sectionHeader}>
          <div>
            <Text className={styles.sectionKicker}>评分解释</Text>
            <Title level={5} className={styles.sectionTitle}>
              六维决策评分
            </Title>
          </div>
          <Text type="secondary">缺失数据保持为空，不按 0 分处理</Text>
        </div>

        <div className={styles.dimensionGrid} style={{ marginTop: 14 }}>
          {Object.entries(item.score_breakdown).map(([key, dimension]) => (
            <div key={key}>
              <div className={styles.dimensionLabel}>
                <span>{DIMENSION_LABELS[key] || key}</span>
                <Text strong>
                  {dimension.score == null ? "证据不足" : `${dimension.score} 分`}
                </Text>
              </div>
              <Progress
                percent={dimension.score ?? 0}
                size="small"
                showInfo={false}
                strokeColor={dimension.score == null ? "#d9d9d9" : "#1677ff"}
              />
              <span className={styles.dimensionReason}>{dimension.reason}</span>
            </div>
          ))}
        </div>

        <div className={styles.detailFacts}>
          <div className={styles.fact}>
            <span className={styles.factLabel}>风险判断</span>
            <span className={styles.factValue}>{item.risk.reason}</span>
          </div>
          <div className={styles.fact}>
            <span className={styles.factLabel}>政策核验</span>
            <span className={styles.factValue}>
              {item.policy_matches.length
                ? policyCountText
                : "具体申报条件待核验"}
            </span>
          </div>
          <div className={styles.fact}>
            <span className={styles.factLabel}>数据缺口</span>
            <span className={styles.factValue} title={unknownText}>{unknownSummary}</span>
          </div>
        </div>

        <AgentVerificationPanel item={item} />

        <div className={styles.detailActions}>
          <Text type="secondary">AI 建议需经人工复核后进入业务流程</Text>
          <Space wrap>
            <Button icon={<FileSearchOutlined />} onClick={onEvidence}>
              查看证据链
            </Button>
            {canWrite && (
              <Button
                type="primary"
                icon={added ? <CheckCircleOutlined /> : <PlusOutlined />}
                disabled={added}
                loading={adding}
                onClick={onAdd}
              >
                {added ? "已加入候选池" : "加入候选池"}
              </Button>
            )}
          </Space>
        </div>
      </div>
    </section>
  );
}

export default function InvestmentDashboard() {
  const { mode, isDemo } = useDataMode();
  const { canAccess } = useUserContext();
  const searchParams = useSearchParams();
  const canWrite = canAccess([
    "super_admin",
    "park_manager",
    "investment_manager",
  ]);
  const [form] = Form.useForm<ScenarioInput>();
  const [activeTab, setActiveTab] = useState("search");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [scenarioId, setScenarioId] = useState("");
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [selected, setSelected] = useState<RecommendationCard | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [addingId, setAddingId] = useState("");
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set());
  const [candidateRefresh, setCandidateRefresh] = useState(0);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [evaluation, setEvaluation] =
    useState<InvestmentEvaluationReport | null>(null);
  const [learningReport, setLearningReport] =
    useState<OfflineLearningReport | null>(null);
  const [urlPrefillDone, setUrlPrefillDone] = useState(false);
  const [weightsOpen, setWeightsOpen] = useState(false);
  const [weightPercent, setWeightPercent] = useState(DEFAULT_WEIGHT_PERCENT);

  const updateWeight = (key: string, nextValue: number) => {
    const keys = Object.keys(weightPercent);
    const otherKeys = keys.filter((item) => item !== key);
    const remaining = 100 - nextValue;
    const currentOtherTotal = otherKeys.reduce((total, item) => total + weightPercent[item], 0);
    const next = { ...weightPercent, [key]: nextValue };
    let assigned = 0;
    otherKeys.forEach((item, index) => {
      const value = index === otherKeys.length - 1
        ? remaining - assigned
        : Math.max(5, Math.round((weightPercent[item] / currentOtherTotal) * remaining));
      next[item] = value;
      assigned += value;
    });
    const total = Object.values(next).reduce((sum, value) => sum + value, 0);
    if (total !== 100) next[otherKeys[otherKeys.length - 1]] += 100 - total;
    setWeightPercent(next);
  };

  // Accept ?scenario=ID from workspace — load pre-created scenario
  useEffect(() => {
    if (urlPrefillDone) return;
    const scenarioParam = searchParams.get("scenario");
    if (!scenarioParam) return;

    setLoading(true);
    setUrlPrefillDone(true);
    getRecommendations(scenarioParam)
      .then((recs) => {
        setScenarioId(scenarioParam);
        setResult(recs);
        setSelected(recs.recommendations[0] || null);
        if (recs.recommendations.length) {
          void recordRecommendationExposure(scenarioParam, mode, "IMPRESSION",
            recs.recommendations.map((item, index) => ({
              enterprise_id: item.enterprise_id, position: index + 1, score: item.overall_score,
            })));
        }
        message.success("已加载工作台同步的招商场景");
      })
      .catch((reason) => {
        message.error(reason instanceof Error ? reason.message : "加载场景失败");
      })
      .finally(() => setLoading(false));
  }, [searchParams, mode, urlPrefillDone]);

  // Accept ?industry=&roles=&location= from workspace — auto-execute scenario
  useEffect(() => {
    if (urlPrefillDone) return;
    const industry = searchParams.get("industry");
    const roles = searchParams.get("roles");
    const location = searchParams.get("location");
    if (!industry && !roles && !location) return;

    const patch: Partial<ScenarioInput> = {};
    if (industry) patch.industry = industry;
    if (roles) {
      patch.target_chain_roles = roles.split(",").map((r) => r.trim()).filter(Boolean);
    }
    if (location) patch.location_preference = location;
    if (industry) {
      patch.name = `${industry}产业招商研判`;
    }

    form.setFieldsValue(patch);
    setUrlPrefillDone(true);
    // Auto-execute: trigger form submission which calls runScenario via onFinish
    setTimeout(() => form.submit(), 100);
  }, [searchParams, form, urlPrefillDone]);

  useEffect(() => {
    void getLatestEvaluation()
      .then(setEvaluation)
      .catch(() => setEvaluation(null));
  }, []);

  useEffect(() => {
    if (!canWrite) return;
    void getOfflineLearningReport(mode)
      .then(setLearningReport)
      .catch(() => setLearningReport(null));
  }, [canWrite, mode]);

  useEffect(() => {
    setResult(null);
    setSelected(null);
    setScenarioId("");
    setAddedIds(new Set());
    setError("");
  }, [mode]);

  const summary = useMemo(() => {
    const recommendations = result?.recommendations || [];
    const evidenceCount = recommendations.reduce(
      (total, item) => total + item.evidence.length,
      0,
    );
    const confidence = recommendations
      .map((item) => item.confidence)
      .filter((value): value is number => value != null);
    return {
      count: recommendations.length,
      evidenceCount,
      averageConfidence: confidence.length
        ? Math.round(
            (confidence.reduce((total, value) => total + value, 0) /
              confidence.length) *
              100,
          )
        : 0,
      unknownRisk: recommendations.filter((item) => item.risk.level === "UNKNOWN")
        .length,
    };
  }, [result]);

  const applyPreset = (preset: (typeof SCENARIO_PRESETS)[number]) => {
    form.setFieldsValue(preset.values);
  };

  const runScenario = async (values: ScenarioInput) => {
    setLoading(true);
    setError("");
    setResult(null);
    setSelected(null);
    setAddedIds(new Set());
    try {
      const created = await createScenario({
        ...values,
        data_mode: mode,
        weights: Object.fromEntries(
          Object.entries(weightPercent).map(([key, value]) => [key, value / 100]),
        ),
      });
      setScenarioId(created.scenario_id);
      const recommendations = await getRecommendations(created.scenario_id);
      setResult(recommendations);
      setSelected(recommendations.recommendations[0] || null);
      if (recommendations.recommendations.length) {
        void recordRecommendationExposure(
          created.scenario_id,
          mode,
          "IMPRESSION",
          recommendations.recommendations.map((item, index) => ({
            enterprise_id: item.enterprise_id,
            position: index + 1,
            score: item.overall_score,
          })),
        );
      }
      message.success("证据化推荐已生成，请复核后加入候选池");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "招商决策任务执行失败");
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (item: RecommendationCard) => {
    if (!scenarioId) return;
    setAddingId(item.enterprise_id);
    try {
      const payload = await addCandidate(scenarioId, item, mode);
      setAddedIds((current) => new Set(current).add(item.enterprise_id));
      setCandidateRefresh((value) => value + 1);
      message.success(
        payload.created ? "已加入招商候选池" : "该企业已在当前候选池中",
      );
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "加入候选池失败");
    } finally {
      setAddingId("");
    }
  };

  const handlePdfExport = async () => {
    if (!scenarioId) return;
    setExportingPdf(true);
    try {
      await downloadScenarioPdf(scenarioId);
      message.success("招商研判 PDF 已生成");
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "PDF 导出失败");
    } finally {
      setExportingPdf(false);
    }
  };

  const handleSelect = (item: RecommendationCard) => {
    setSelected(item);
    const position =
      (result?.recommendations.findIndex(
        (candidate) => candidate.enterprise_id === item.enterprise_id,
      ) ?? 0) + 1;
    if (scenarioId) {
      void recordRecommendationExposure(scenarioId, mode, "SELECT", [
        {
          enterprise_id: item.enterprise_id,
          position,
          score: item.overall_score,
        },
      ]);
    }
  };

  return (
    <div className={styles.dashboard}>
      <PageHeader
        title="招商决策中心"
        description="围绕广州机器人产业园，完成公开快照召回、证据化评分、候选入池、负责人分配与人工复核"
        backLabel="返回园区运营总览"
        extra={
          <Space wrap>
            <Button href="/management/documents" icon={<FileSearchOutlined />}>导入园区资料</Button>
            <Button icon={<SettingOutlined />} onClick={() => setWeightsOpen(true)}>评分权重</Button>
          </Space>
        }
      />

      <div className={styles.hero}>
        <div className={styles.heroContent}>
          <div>
            <span className={styles.heroEyebrow}>
              <ThunderboltOutlined /> Industrial AI Decision Workspace
            </span>
            <Title level={3} className={styles.heroTitle}>
              从企业线索到可执行招商动作
            </Title>
            <Paragraph className={styles.heroDescription}>
              统一比较推荐优先级、证据覆盖与风险边界。系统只生成建议，
              入池和复核始终由招商人员确认。
            </Paragraph>
          </div>
          <span className={styles.modeBadge}>
            {isDemo ? "演示沙盘 · 数据隔离" : "公开快照 · 可追溯"}
          </span>
        </div>
      </div>

      <Tabs
        className={styles.tabs}
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "search",
            label: (
              <span>
                <RobotOutlined /> AI 寻商
              </span>
            ),
            children: (
              <>
                <Card className={styles.missionCard}>
                  <div className={styles.missionHeader}>
                    <div>
                      <Text className={styles.sectionKicker}>任务配置</Text>
                      <Title level={4} className={styles.sectionTitle}>
                        定义本次寻商目标
                      </Title>
                      <Text type="secondary">
                        选择预设或调整产业环节，生成一组可比较的候选建议
                      </Text>
                    </div>
                    <Tag
                      icon={
                        isDemo ? <ExperimentOutlined /> : <SafetyCertificateOutlined />
                      }
                      color={isDemo ? "orange" : "blue"}
                    >
                      {isDemo ? "演示数据" : "公开数据"}
                    </Tag>
                  </div>

                  <div className={styles.presetRow}>
                    <Space wrap size={[8, 8]}>
                      <span className={styles.presetLabel}>快速策略</span>
                      {SCENARIO_PRESETS.map((preset) => (
                        <Button
                          key={preset.label}
                          size="small"
                          onClick={() => applyPreset(preset)}
                        >
                          {preset.label}
                        </Button>
                      ))}
                    </Space>
                  </div>

                  <Form
                    form={form}
                    layout="vertical"
                    initialValues={{
                      name: "广州机器人产业园招商",
                      industry: "机器人",
                      target_chain_roles: ["核心零部件", "系统集成", "工业软件"],
                      location_preference: "广州",
                      limit: 5,
                    }}
                    onFinish={(values) =>
                      void runScenario({ ...values, data_mode: mode })
                    }
                  >
                    <Row gutter={16}>
                      <Col xs={24} lg={6}>
                        <Form.Item
                          name="name"
                          label="任务名称"
                          rules={[{ required: true, message: "请输入任务名称" }]}
                        >
                          <Input placeholder="例如：机器人产业补链行动" />
                        </Form.Item>
                      </Col>
                      <Col xs={24} sm={12} lg={4}>
                        <Form.Item
                          name="industry"
                          label="产业方向"
                          rules={[{ required: true, message: "请输入产业方向" }]}
                        >
                          <Input placeholder="机器人" />
                        </Form.Item>
                      </Col>
                      <Col xs={24} lg={7}>
                        <Form.Item
                          name="target_chain_roles"
                          label="目标产业链环节"
                          rules={[{ required: true, message: "至少选择一个环节" }]}
                        >
                          <Select
                            mode="tags"
                            placeholder="选择或输入产业链环节"
                            tokenSeparators={[",", "，"]}
                            options={[
                              { value: "核心零部件" },
                              { value: "系统集成" },
                              { value: "工业软件" },
                              { value: "机器视觉" },
                              { value: "伺服与驱动" },
                            ]}
                          />
                        </Form.Item>
                      </Col>
                      <Col xs={14} sm={8} lg={3}>
                        <Form.Item name="location_preference" label="地域偏好">
                          <Input placeholder="广州" />
                        </Form.Item>
                      </Col>
                      <Col xs={10} sm={4} lg={2}>
                        <Form.Item name="limit" label="返回数">
                          <InputNumber min={1} max={10} style={{ width: "100%" }} />
                        </Form.Item>
                      </Col>
                      <Col xs={24} lg={2}>
                        <Form.Item label=" ">
                          <Button
                            className={styles.runButton}
                            type="primary"
                            htmlType="submit"
                            icon={<PlayCircleOutlined />}
                            loading={loading}
                            block
                          >
                            启动
                          </Button>
                        </Form.Item>
                      </Col>
                    </Row>
                  </Form>
                </Card>

                {(loading || result) && (
                  <div className={styles.pipeline} aria-label="决策流水线">
                    {["场景解析", "证据召回", "规范化评分", "人工决策"].map(
                      (label, index) => (
                        <div
                          key={label}
                          data-step={index + 1}
                          className={`${styles.pipelineStep} ${
                            result || (loading && index < 3)
                              ? styles.pipelineActive
                              : ""
                          }`}
                        >
                          {label}
                        </div>
                      ),
                    )}
                  </div>
                )}

                {error && (
                  <Alert
                    type="error"
                    showIcon
                    message={error}
                    description="请确认数据库迁移已完成、持久化服务可用，且当前账号拥有招商写权限。"
                    style={{ marginBottom: 16 }}
                  />
                )}

                {loading ? (
                  <div className={styles.emptyState}>
                    <Spin size="large" />
                    <Title level={5} style={{ marginTop: 18 }}>
                      正在形成可比较的招商建议
                    </Title>
                    <Text type="secondary">
                      召回企业快照、校验证据，并生成结构化评分与行动建议
                    </Text>
                  </div>
                ) : result ? (
                  result.recommendations.length ? (
                    <>
                      <div className={styles.summaryStrip}>
                        <div className={styles.summaryItem}>
                          <span className={styles.summaryLabel}>候选建议</span>
                          <span className={styles.summaryValue}>{summary.count} 家</span>
                        </div>
                        <div className={styles.summaryItem}>
                          <span className={styles.summaryLabel}>证据条目</span>
                          <span className={styles.summaryValue}>
                            {summary.evidenceCount} 条
                          </span>
                        </div>
                        <div className={styles.summaryItem}>
                          <span className={styles.summaryLabel}>平均置信度</span>
                          <span className={styles.summaryValue}>
                            {summary.averageConfidence}%
                          </span>
                        </div>
                        <div className={styles.summaryItem}>
                          <span className={styles.summaryLabel}>风险待核验</span>
                          <span className={styles.summaryValue}>
                            {summary.unknownRisk} 家
                          </span>
                        </div>
                      </div>

                      <div className={styles.resultToolbar}>
                        <Text type="secondary">
                          PDF 严格使用当前场景快照，不会重新调用 Agent。
                        </Text>
                        <Button
                          icon={<DownloadOutlined />}
                          loading={exportingPdf}
                          onClick={() => void handlePdfExport()}
                        >
                          导出招商研判 PDF
                        </Button>
                      </div>

                      <div className={styles.workspace}>
                        <RecommendationRanking
                          recommendations={result.recommendations}
                          selectedId={selected?.enterprise_id}
                          onSelect={handleSelect}
                        />
                        {selected && (
                          <RecommendationDetail
                            item={selected}
                            canWrite={canWrite}
                            added={addedIds.has(selected.enterprise_id)}
                            adding={addingId === selected.enterprise_id}
                            onEvidence={() => setEvidenceOpen(true)}
                            onAdd={() => void handleAdd(selected)}
                          />
                        )}
                      </div>
                    </>
                  ) : (
                    <div className={styles.emptyState}>
                      <Empty
                        description="当前快照未召回可评分企业，请调整产业链环节"
                      >
                        <Button type="primary" onClick={() => form.focusField("target_chain_roles")}>
                          调整寻商条件
                        </Button>
                      </Empty>
                    </div>
                  )
                ) : (
                  <div className={styles.emptyState}>
                    <RobotOutlined style={{ fontSize: 34, color: "#1677ff" }} />
                    <Title level={4} style={{ margin: "14px 0 6px" }}>
                      配置目标，开始一次证据化寻商
                    </Title>
                    <Text type="secondary">
                      推荐结果将按优先级排列，并保留评分依据、数据缺口和风险边界
                    </Text>
                  </div>
                )}
              </>
            ),
          },
          {
            key: "candidates",
            label: (
              <span>
                <AuditOutlined /> 招商候选池
              </span>
            ),
            children: (
              <CandidatePool
                mode={mode}
                canWrite={canWrite}
                refreshToken={candidateRefresh}
              />
            ),
          },
          {
            key: "evaluation",
            label: (
              <span>
                <SafetyCertificateOutlined /> 评测说明
              </span>
            ),
            children: (
              <Row gutter={[16, 16]}>
                {evaluation && (
                  <Col span={24}>
                    <Card
                      title="30家公开企业自动评测"
                      className={styles.poolCard}
                      extra={
                        <Tag color={evaluation.passed ? "success" : "error"}>
                          {evaluation.passed ? "全部通过" : "存在失败项"}
                        </Tag>
                      }
                    >
                      <div className={styles.evaluationGrid}>
                        {[
                          ["公开样本", evaluation.metrics.dataset_size, "家"],
                          [
                            "来源可追溯",
                            evaluation.metrics.source_traceability_rate,
                            "%",
                          ],
                          [
                            "证据链接",
                            evaluation.metrics.evidence_linkage_rate,
                            "%",
                          ],
                          [
                            "缺失值非零化",
                            evaluation.metrics.missing_value_integrity_rate,
                            "%",
                          ],
                          [
                            "风险 UNKNOWN 边界",
                            evaluation.metrics.risk_unknown_integrity_rate,
                            "%",
                          ],
                          [
                            "确定性重复",
                            evaluation.metrics.deterministic_repeat_rate,
                            "%",
                          ],
                        ].map(([label, value, unit]) => (
                          <div className={styles.evaluationMetric} key={String(label)}>
                            <span>{label}</span>
                            <strong>
                              {value}
                              {unit}
                            </strong>
                          </div>
                        ))}
                      </div>
                      <Alert
                        type="info"
                        showIcon
                        message="评测边界"
                        description={evaluation.scope}
                        style={{ marginTop: 14 }}
                      />
                    </Card>
                  </Col>
                )}
                {learningReport && (
                  <Col span={24}>
                    <Card
                      title="人工反馈与离线排序学习"
                      className={styles.poolCard}
                      extra={
                        <Tag color={learningReport.ready ? "processing" : "default"}>
                          {learningReport.ready ? "可进入离线回放" : "样本积累中"}
                        </Tag>
                      }
                    >
                      <Row gutter={[12, 12]}>
                        {[
                          ["曝光", learningReport.sample.impressions],
                          ["有效反馈", learningReport.sample.labeled_feedback],
                          ["接受", learningReport.sample.accepted],
                          ["拒绝", learningReport.sample.rejected],
                        ].map(([label, value]) => (
                          <Col xs={12} md={6} key={String(label)}>
                            <div className={styles.poolMetric}>
                              <span className={styles.poolMetricValue}>{value}</span>
                              <span className={styles.poolMetricLabel}>{label}</span>
                            </div>
                          </Col>
                        ))}
                      </Row>
                      <Alert
                        type={learningReport.ready ? "warning" : "info"}
                        showIcon
                        message={learningReport.reason}
                        description="系统只生成可审查的离线权重候选，不会自动修改线上评分或推荐顺序。"
                        style={{ marginTop: 12 }}
                      />
                    </Card>
                  </Col>
                )}
                <Col xs={24} lg={12}>
                  <Card title="评分合同" className={styles.poolCard}>
                    <Descriptions bordered column={1} size="small">
                      <Descriptions.Item label="产业匹配度">30%</Descriptions.Item>
                      <Descriptions.Item label="技术能力">20%</Descriptions.Item>
                      <Descriptions.Item label="成长潜力">15%</Descriptions.Item>
                      <Descriptions.Item label="落地意愿">10%</Descriptions.Item>
                      <Descriptions.Item label="政策适配度">15%</Descriptions.Item>
                      <Descriptions.Item label="数据完整度">10%</Descriptions.Item>
                    </Descriptions>
                    <Alert
                      type="info"
                      showIcon
                      message="权重是可配置产品假设"
                      description="只对有合法证据的维度重新归一化；缺失值保持为空，不能按 0 分处理。"
                      style={{ marginTop: 16 }}
                    />
                  </Card>
                </Col>
                <Col xs={24} lg={12}>
                  <Card title="真实性边界" className={styles.poolCard}>
                    <List
                      dataSource={[
                        "模型总结不是来源，每个评分维度必须引用证据 ID。",
                        "未发现风险记录必须显示 UNKNOWN，不得显示低风险。",
                        "政策相关不等于满足申报条件。",
                        "演示沙盘持续显示标识，并与公开候选逻辑隔离。",
                        "AI 推荐不会自动写入候选池，必须由用户明确确认。",
                        "人工反馈不修改原始公开数据。",
                      ]}
                      renderItem={(item) => (
                        <List.Item>
                          <CheckCircleOutlined
                            style={{ color: "#1677ff", marginRight: 10 }}
                          />
                          {item}
                        </List.Item>
                      )}
                    />
                  </Card>
                </Col>
                {result && (
                  <Col span={24}>
                    <Card
                      title={`本次运行 · ${result.version}`}
                      className={styles.poolCard}
                    >
                      <Row gutter={24}>
                        <Col xs={24} lg={10}>
                          <Descriptions size="small" column={1}>
                            <Descriptions.Item label="场景 ID">
                              <Text copyable>{result.scenario_id}</Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="生成时间">
                              {new Date(result.generated_at).toLocaleString("zh-CN")}
                            </Descriptions.Item>
                            {Object.entries(result.source_summary).map(([key, value]) => (
                              <Descriptions.Item key={key} label={key}>
                                {typeof value === "object"
                                  ? JSON.stringify(value)
                                  : String(value ?? "—")}
                              </Descriptions.Item>
                            ))}
                          </Descriptions>
                        </Col>
                        <Col xs={24} lg={14}>
                          <Alert
                            type="warning"
                            showIcon
                            message="已知限制"
                            description={
                              <ul style={{ margin: 0, paddingLeft: 18 }}>
                                {result.limitations.map((item) => (
                                  <li key={item}>{item}</li>
                                ))}
                              </ul>
                            }
                          />
                        </Col>
                      </Row>
                    </Card>
                  </Col>
                )}
              </Row>
            ),
          },
        ]}
      />

      <EvidenceDrawer
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        title={selected?.enterprise_name || "推荐企业"}
        evidence={selected?.evidence || []}
        unknownFields={selected?.unknown_fields || []}
        warnings={selected?.warnings || []}
      />

      <Drawer
        title="六维推荐评分权重"
        width={460}
        open={weightsOpen}
        onClose={() => setWeightsOpen(false)}
        extra={<Tag color="processing">总计 100%</Tag>}
      >
        <Alert
          type="info"
          showIcon
          message="推荐分如何计算"
          description="每个维度先依据可追溯证据得到 0–100 分，再按下方权重加权。证据缺失的维度保持为空，系统只在有证据的维度中重新归一化，不会把未知当成 0 分。"
          style={{ marginBottom: 22 }}
        />
        <div className={styles.weightEditor}>
          {Object.entries(weightPercent).map(([key, value]) => (
            <div className={styles.weightRow} key={key}>
              <div className={styles.weightRowHead}>
                <strong>{DIMENSION_LABELS[key]}</strong>
                <span>{value}%</span>
              </div>
              <Slider
                min={5}
                max={50}
                value={value}
                tooltip={{ formatter: (current) => `${current}%` }}
                onChange={(current) => updateWeight(key, current)}
              />
            </div>
          ))}
        </div>
        <Alert
          type="warning"
          showIcon
          message="权重改变的是优先级，不改变原始证据"
          description="修改后需要重新启动寻商，系统会按照本次权重生成新的推荐快照和排序；已保存的历史场景不会被覆盖。"
          style={{ marginTop: 18 }}
        />
        <Space style={{ marginTop: 20 }}>
          <Button onClick={() => setWeightPercent(DEFAULT_WEIGHT_PERCENT)}>恢复默认</Button>
          <Button type="primary" onClick={() => setWeightsOpen(false)}>应用到下次寻商</Button>
        </Space>
      </Drawer>
    </div>
  );
}
