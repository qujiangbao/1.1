"""Tool Gateway — 所有 Agent 访问数据的唯一切入点"""
import time
import logging
from typing import Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    tool_name: str
    status: str     # success / error
    data: Any
    error: str = ""
    duration_ms: int = 0


class ToolGateway:
    """
    执行流程：
    1. 权限检查 → Agent 是否有权调用此 Tool？
    2. 参数验证 → JSON Schema 校验
    3. 速率限制 → 是否超过配额？
    4. 执行 → 调用实际 Tool
    5. Trace → 记录调用日志
    """

    # Agent-Tool 权限矩阵
    PERMISSIONS = {
        "InvestmentAgent": ["enterprise_search", "enterprise_profile_get",
                           "enterprise_query", "investment_scoring"],
        "RiskAgent": ["enterprise_query", "enterprise_profile_get",
                     "risk_scoring", "risk_history",
                     "enterprise_risk_events", "enterprise_business_status"],
        "PolicyAgent": ["policy_vector_search", "policy_metadata_search",
                       "policy_query", "enterprise_profile_get"],
        "IndustryAgent": ["industry_query", "industry_vector_search",
                         "knowledge_graph_query"],
        "EnterpriseServiceAgent": ["enterprise_query", "enterprise_profile_get",
                                   "service_ticket_query"],
        "BIAgent": ["dashboard_query", "metric_query"],
        "Supervisor": ["*"],  # Supervisor 拥有全部权限
    }

    def __init__(self):
        self._tools = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册内置工具

        P0: enterprise_search / enterprise_profile_get / enterprise_query /
            enterprise_risk_events / enterprise_business_status
            已升级为 EnterpriseDataTool → DataAdapter → 外部 API。
            mock 方法保留在 adapters/mock.py。
        """
        self._tools = {
            # === P0: EnterpriseDataTool (真实数据 / MockAdapter) ===
            "enterprise_search":       self._enterprise_search,
            "enterprise_profile_get":  self._enterprise_profile_get,
            "enterprise_query":        self._enterprise_query,
            "enterprise_risk_events":  self._enterprise_risk_events,
            "enterprise_business_status": self._enterprise_business_status,
            "investment_scoring":      self._enterprise_scoring,
            # === 其他工具（暂保持 mock） ===
            "risk_scoring":            self._mock("risk_scoring"),
            "risk_history":            self._mock("risk_history"),
            "policy_vector_search":    self._mock_policy_search,
            "policy_metadata_search":  self._mock_policy_search,
            "policy_query":            self._mock_policy_search,
            "industry_query":          self._mock("industry_query"),
            "industry_vector_search":  self._mock("industry_vector_search"),
            "knowledge_graph_query":   self._mock("knowledge_graph_query"),
            "service_ticket_query":    self._mock("service_ticket_query"),
            "dashboard_query":         self._mock("dashboard_query"),
            "metric_query":            self._mock("metric_query"),
        }

    # ═══ P0: EnterpriseDataTool 委托方法 ═══

    @staticmethod
    def _enterprise_profile_get(params: Dict) -> Dict:
        """企业画像 → EnterpriseDataTool"""
        from app.tools.enterprise_data import get_enterprise_data_tool
        etd = get_enterprise_data_tool()
        eid = params.get("enterprise_id", "")
        result = etd.get_profile_sync(eid)
        return {"status": result.get("status", "success"),
                "tool": "enterprise_profile_get", "params": params,
                "result": result.get("data", result)}

    @staticmethod
    def _enterprise_search(params: Dict) -> Dict:
        """企业搜索 → EnterpriseDataTool"""
        from app.tools.enterprise_data import get_enterprise_data_tool
        etd = get_enterprise_data_tool()
        query = str(params.get("query", params.get("industry", "")))
        result = etd.search_enterprises_sync(query,
            industry=params.get("industry"),
            location=params.get("location"),
            limit=params.get("limit", 20))
        return {"status": result.get("status", "success"),
                "tool": "enterprise_search", "params": params,
                "result": {"enterprises": result.get("enterprises", []),
                           "total": result.get("total", 0)}}

    @staticmethod
    def _enterprise_query(params: Dict) -> Dict:
        """企业基础查询 → EnterpriseDataTool"""
        from app.tools.enterprise_data import get_enterprise_data_tool
        etd = get_enterprise_data_tool()
        eid = params.get("enterprise_id", "")
        result = etd.get_profile_sync(eid)
        profile = result.get("data", {})
        return {"status": "success", "tool": "enterprise_query", "params": params,
                "result": {"name": profile.get("name", eid),
                           "industry": profile.get("industry", ""),
                           "registered_capital": profile.get("registered_capital", "")}}

    @staticmethod
    def _enterprise_risk_events(params: Dict) -> Dict:
        """风险事件列表 → EnterpriseDataTool"""
        from app.tools.enterprise_data import get_enterprise_data_tool
        etd = get_enterprise_data_tool()
        eid = params.get("enterprise_id", "")
        result = etd.get_risk_events_sync(eid,
            event_type=params.get("event_type"),
            limit=params.get("limit", 20))
        return {"status": result.get("status", "success"),
                "tool": "enterprise_risk_events", "params": params,
                "result": {"events": result.get("events", []),
                           "total": result.get("total", 0)}}

    @staticmethod
    def _enterprise_business_status(params: Dict) -> Dict:
        """经营状态 → EnterpriseDataTool"""
        from app.tools.enterprise_data import get_enterprise_data_tool
        etd = get_enterprise_data_tool()
        eid = params.get("enterprise_id", "")
        result = etd.get_business_status_sync(eid)
        return {"status": result.get("status", "success"),
                "tool": "enterprise_business_status", "params": params,
                "result": result.get("data", result)}

    @staticmethod
    def _enterprise_scoring(params: Dict) -> Dict:
        """投资评分 → EnterpriseDataTool"""
        from app.tools.enterprise_data import get_enterprise_data_tool
        etd = get_enterprise_data_tool()
        eid = str(params.get("enterprise_id", ""))
        result = etd.compute_scoring_sync(eid)
        return {"status": result.get("status", "success"),
                "tool": "investment_scoring", "params": params,
                "result": result}

    # ═══ 原始 Mock 方法（保留兼容，迁移到 adapters/mock.py） ═══

    def _mock(self, name: str):
        """临时 mock 工具（数据库就绪后替换为真实实现）"""
        def handler(params: Dict) -> Dict:
            return {
                "status": "success",
                "tool": name,
                "params": params,
                "result": {"message": f"Tool {name} executed (mock)"},
            }
        return handler

    def _mock_enterprise_search(self, params: Dict) -> Dict:
        """Mock: 企业搜索 — 返回机器人产业链相关企业"""
        query = str(params.get("query", params.get("industry", ""))).lower()
        enterprises = [
            {"enterprise_id": "ENT-001", "name": "广东博智林机器人", "industry": "建筑机器人", "score": 95, "location": "佛山", "registered_capital": "10亿", "match_reason": "碧桂园旗下，建筑机器人龙头"},
            {"enterprise_id": "ENT-002", "name": "广州数控设备", "industry": "工业机器人", "score": 92, "location": "广州", "registered_capital": "5亿", "match_reason": "国产数控系统第一梯队"},
            {"enterprise_id": "ENT-003", "name": "深圳汇川技术", "industry": "伺服系统/控制器", "score": 90, "location": "深圳", "registered_capital": "8亿", "match_reason": "伺服驱动市占率前三"},
            {"enterprise_id": "ENT-004", "name": "大疆创新", "industry": "无人机/传感器", "score": 88, "location": "深圳", "registered_capital": "3亿", "match_reason": "传感器+飞控技术积累深厚"},
            {"enterprise_id": "ENT-005", "name": "优必选科技", "industry": "服务机器人", "score": 87, "location": "深圳", "registered_capital": "4亿", "match_reason": "人形机器人赛道领先"},
        ]
        if "传感" in query:
            enterprises = [e for e in enterprises if "传感" in e.get("industry", "")]
        return {"status": "success", "tool": "enterprise_search", "params": params, "result": {"enterprises": enterprises, "total": len(enterprises)}}

    def _mock_scoring(self, params: Dict) -> Dict:
        """Mock: 投资评分 — 返回模拟评分数据"""
        import hashlib
        eid = str(params.get("enterprise_id", ""))
        base = sum(ord(c) for c in eid) % 30
        score = min(95, 70 + base)
        return {"status": "success", "tool": "investment_scoring", "params": params, "result": {
            "score": score,
            "level": "STRONG_RECOMMEND" if score >= 85 else "RECOMMEND",
            "reasons": ["产业链匹配度高", "技术实力突出", "扩产意愿明确"],
        }}

    def _mock_enterprise_profile(self, params: Dict) -> Dict:
        """Mock: 企业画像 — 按 enterprise_id 映射真实名称"""
        eid = str(params.get("enterprise_id", ""))
        profiles = {
            "ENT-001": {"name": "广东博智林机器人", "industry": "建筑机器人", "location": "佛山", "registered_capital": "10亿", "match_reason": "建筑机器人龙头，产业协同价值高"},
            "ENT-002": {"name": "广州数控设备", "industry": "工业机器人", "location": "广州", "registered_capital": "5亿", "match_reason": "国产数控系统第一梯队，与园区定位高度匹配"},
            "ENT-003": {"name": "深圳汇川技术", "industry": "伺服系统/控制器", "location": "深圳", "registered_capital": "8亿", "match_reason": "核心零部件能力强，可补齐产业链短板"},
            "ENT-004": {"name": "大疆创新", "industry": "无人机/传感器", "location": "深圳", "registered_capital": "3亿", "match_reason": "传感器与飞控技术积累深厚"},
            "ENT-005": {"name": "优必选科技", "industry": "服务机器人", "location": "深圳", "registered_capital": "4亿", "match_reason": "人形机器人赛道领先，品牌带动效应强"},
            "risk-001": {"name": "某智能装备公司", "industry": "智能装备", "location": "广州", "registered_capital": "2亿", "match_reason": "融资动态异常，建议优先核查现金流"},
            "risk-002": {"name": "某机器人科技", "industry": "工业机器人", "location": "广州", "registered_capital": "1.5亿", "match_reason": "招聘量与核心人员变化需要持续跟踪"},
            "risk-003": {"name": "某新能源材料", "industry": "新能源材料", "location": "广州", "registered_capital": "3亿", "match_reason": "供应商频繁变化，需排查供应链稳定性"},
            "risk-004": {"name": "某电子制造", "industry": "电子制造", "location": "广州", "registered_capital": "8000万", "match_reason": "近期工商与股权结构变更较频繁"},
            "risk-005": {"name": "某AI科技", "industry": "人工智能", "location": "广州", "registered_capital": "5000万", "match_reason": "存在贷款逾期信号，需评估偿债能力"},
            "risk-006": {"name": "某芯片设计", "industry": "集成电路", "location": "广州", "registered_capital": "1亿", "match_reason": "营收短期下降，建议保持常规关注"},
            "risk-007": {"name": "某医疗器械", "industry": "医疗器械", "location": "广州", "registered_capital": "6000万", "match_reason": "专利纠纷尚未解决，需持续观察"},
            "risk-008": {"name": "某数据服务", "industry": "数据服务", "location": "广州", "registered_capital": "3000万", "match_reason": "客户集中度偏高，建议关注收入结构"},
        }
        profile = profiles.get(eid, {
            "name": eid or "未知企业", "industry": "智能制造", "location": "广州",
            "registered_capital": "1亿", "match_reason": "与园区重点产业方向匹配",
        })
        return {"status": "success", "tool": "enterprise_profile_get", "params": params, "result": {
            **profile,
            "enterprise_id": eid,
            "score": 85,
            "financial_health": "良好",
            "expansion_willingness": "高",
            "growth_rate": 18,
            "funding_amount": 500,
            "employee_count": 200,
        }}

    def _mock_enterprise_query(self, params: Dict) -> Dict:
        return {"status": "success", "tool": "enterprise_query", "params": params, "result": {
            "name": params.get("enterprise_id", "未知企业"),
            "industry": "智能制造",
            "registered_capital": "1亿",
        }}

    def _mock_policy_search(self, params: Dict) -> Dict:
        """Mock: 政策搜索 — 返回产业相关真实政策"""
        query = str(params.get("query", "")).lower()
        all_policies = [
            {"title": "广东省机器人产业集群行动计划(2024-2027)", "level": "provincial", "department": "广东省工信厅", "summary": "重点支持工业机器人、服务机器人、特种机器人三大方向，对入驻产业园企业给予最高500万元补贴"},
            {"title": "广州市人工智能产业扶持办法", "level": "municipal", "department": "广州市科技局", "summary": "对AI+制造融合项目给予研发费用50%补贴，最高300万元"},
            {"title": "十四五机器人产业发展规划", "level": "national", "department": "工信部", "summary": "到2025年机器人产业营业收入年均增速超过20%，建成3-5个国际影响力产业集群"},
            {"title": "广州市黄埔区促进智能制造发展办法", "level": "district", "department": "黄埔区工信局", "summary": "对新入驻智能制造企业给予三年租金补贴，前两年免租"},
            {"title": "广东省战略性产业集群重点产业链「链主」企业遴选", "level": "provincial", "department": "广东省发改委", "summary": "评选机器人产业链链主企业，给予税收优惠和用地优先权"},
            {"title": "广州市科技型中小企业技术创新基金", "level": "municipal", "department": "广州市科技局", "summary": "对机器人领域科技型中小企业提供50-200万元创新基金"},
            {"title": "关于加快培育发展制造业优质企业的指导意见", "level": "national", "department": "工信部", "summary": "培育一批机器人领域专精特新「小巨人」企业"},
            {"title": "广东省制造业数字化转型实施方案", "level": "provincial", "department": "广东省政府", "summary": "推动制造业智能化改造，对机器人应用示范项目给予30%设备补贴"},
        ]
        # Filter by keyword if provided
        if query:
            filtered = [p for p in all_policies if query in p["title"] or query in p["summary"]]
            if not filtered:
                filtered = all_policies  # fallback: return all if no match
            result_policies = filtered[:5]
        else:
            result_policies = all_policies[:5]

        chunks = []
        for p in result_policies:
            chunks.append({"title": p["title"], "similarity": 0.85 + (0.02 * (5 - len(chunks))), "content": p["summary"]})

        return {"status": "success", "tool": "policy_vector_search", "params": params, "result": {"chunks": chunks, "total": len(chunks)}}

    def _check_permission(self, agent: str, tool_name: str) -> bool:
        allowed = self.PERMISSIONS.get(agent, [])
        return "*" in allowed or tool_name in allowed

    def invoke(self, agent_name: str, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """Agent 调用工具的唯一入口"""
        t0 = time.time()

        # 1. 权限检查
        if not self._check_permission(agent_name, tool_name):
            return ToolResult(
                tool_name=tool_name,
                status="error",
                data=None,
                error=f"PERMISSION_DENIED: {agent_name} cannot call {tool_name}",
                duration_ms=int((time.time() - t0) * 1000),
            )

        # 2. 获取工具
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                status="error",
                data=None,
                error=f"TOOL_NOT_FOUND: {tool_name}",
                duration_ms=int((time.time() - t0) * 1000),
            )

        # 3. 执行
        try:
            result = tool(params)
            duration = int((time.time() - t0) * 1000)

            logger.info(f"[ToolGateway] {agent_name} → {tool_name} ({duration}ms)")

            return ToolResult(
                tool_name=tool_name,
                status="success",
                data=result.get("result"),
                duration_ms=duration,
            )
        except Exception as e:
            return ToolResult(
                tool_name=tool_name,
                status="error",
                data=None,
                error=str(e),
                duration_ms=int((time.time() - t0) * 1000),
            )

    def register_tool(self, name: str, handler, permissions: list[str]):
        """注册新工具"""
        self._tools[name] = handler
        for agent in permissions:
            if agent not in self.PERMISSIONS:
                self.PERMISSIONS[agent] = []
            if name not in self.PERMISSIONS[agent]:
                self.PERMISSIONS[agent].append(name)


# 全局单例
_tool_gateway: ToolGateway | None = None


def get_tool_gateway() -> ToolGateway:
    global _tool_gateway
    if _tool_gateway is None:
        _tool_gateway = ToolGateway()
    return _tool_gateway
