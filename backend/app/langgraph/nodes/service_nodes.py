"""Enterprise Service Agent Nodes"""
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from app.tools.gateway import get_tool_gateway

tg = get_tool_gateway()

SERVICE_CATALOG = {
    "policy_service":     {"name": "政策服务", "agent": "PolicyAgent"},
    "talent_service":     {"name": "人才服务", "agent": None},
    "finance_service":    {"name": "金融服务", "agent": None},
    "technology_service": {"name": "技术服务", "agent": "IndustryAgent"},
    "market_service":     {"name": "市场服务", "agent": "IndustryAgent"},
    "space_service":      {"name": "空间服务", "agent": None},
    "government_service": {"name": "政务服务", "agent": "PolicyAgent"},
    "growth_service":     {"name": "成长服务", "agent": None},
}

SERVICE_KEYWORDS = {
    "policy_service": ("政策", "补贴", "申报", "资助"),
    "talent_service": ("人才", "招聘", "用工", "员工"),
    "finance_service": ("融资", "贷款", "基金", "授信"),
    "technology_service": ("技术", "研发", "中试", "检测", "实验室"),
    "market_service": ("市场", "客户", "订单", "供需", "展会"),
    "space_service": ("报修", "物业", "空调", "水电", "停车", "会议室", "场地", "搬迁", "增容"),
    "government_service": ("政务", "工商", "税务", "许可证", "入驻手续"),
    "growth_service": ("成长", "培训", "管理咨询"),
}

SERVICE_NEXT_STEPS = {
    "policy_service": ["整理企业基本信息和拟申报事项", "交由政策服务人员核验申报资格"],
    "talent_service": ["补充岗位、人数和到岗时间", "交由人才服务人员登记招聘需求"],
    "finance_service": ["补充融资用途、金额和期限", "交由金融服务人员开展合规对接"],
    "technology_service": ["补充技术目标、设备和验收要求", "交由技术服务人员安排评估"],
    "market_service": ["补充目标客户和合作场景", "交由企业服务人员安排供需对接"],
    "space_service": ["补充楼栋、房间和现场联系人", "在园区正式物业工单系统中登记"],
    "government_service": ["补充办理事项和材料清单", "交由政务服务人员人工受理"],
    "growth_service": ["补充企业阶段和具体目标", "交由企业服务人员制定支持计划"],
}


class ServiceState(TypedDict):
    task_id: str
    input: Dict[str, Any]
    enterprise_id: str
    request: str
    priority: str
    intent: str
    service_category: str
    sub_services: List[str]
    ticket_id: Optional[str]
    lifecycle_stage: str
    agent_results: Dict[str, Dict]
    final_response: Optional[Dict]
    status: str
    tools_used: List[str]


def intent_analyzer(state: ServiceState) -> ServiceState:
    inp = state.get("input", {})
    state["request"] = inp.get("request", "")
    state["enterprise_id"] = inp.get("enterprise_id", "")
    state["intent"] = "service_request"
    request = state["request"].lower()
    category = next(
        (
            name
            for name, keywords in SERVICE_KEYWORDS.items()
            if any(keyword in request for keyword in keywords)
        ),
        "growth_service",
    )
    state["service_category"] = category
    state["sub_services"] = [category]
    state["lifecycle_stage"] = "growing"
    state["tools_used"] = []
    state["status"] = "ticketing"
    return state


def ticket_manager(state: ServiceState) -> ServiceState:
    # The formal workbench is persistent, but an AI conversation must not
    # create an operational obligation without an explicit user submission.
    state["ticket_id"] = None
    state["status"] = "advising"
    return state


def workflow_engine(state: ServiceState) -> ServiceState:
    results = {}
    for svc in state.get("sub_services", []):
        cat = SERVICE_CATALOG.get(svc, {})
        results[svc] = {
            "service": cat.get("name", svc),
            "agent": cat.get("agent"),
            "status": "advice_only",
            "result": {"summary": f"已识别为{cat.get('name', svc)}需求，可在企业服务工单中登记"},
        }
    state["agent_results"] = results
    state["status"] = "aggregating"
    return state


def result_aggregator(state: ServiceState) -> ServiceState:
    category = state["service_category"]
    state["final_response"] = {
        "ticket_id": None,
        "ticket_created": False,
        "request_received": True,
        "service_category": category,
        "service_name": SERVICE_CATALOG.get(category, {}).get("name", "企业服务"),
        "results": state["agent_results"],
        "next_steps": SERVICE_NEXT_STEPS.get(category, ["交由企业服务人员人工登记"]),
        "notice": "已接入正式企业服务工单工作台；本次对话仅做分类，需用户明确提交后才创建业务工单。",
    }
    state["status"] = "done"
    return state


def build_service_graph():
    w = StateGraph(ServiceState)
    for n, f in [("intent_analyzer", intent_analyzer), ("ticket", ticket_manager),
                  ("workflow", workflow_engine), ("aggregator", result_aggregator)]:
        w.add_node(n, f)
    w.set_entry_point("intent_analyzer")
    for a, b in [("intent_analyzer","ticket"),("ticket","workflow"),("workflow","aggregator")]:
        w.add_edge(a, b)
    w.add_edge("aggregator", END)
    return w.compile()

_sg = None
def get_service_graph():
    global _sg
    if _sg is None: _sg = build_service_graph()
    return _sg
