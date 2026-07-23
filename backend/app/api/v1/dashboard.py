"""Dashboard API — KPI + BI 驾驶舱"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard/kpi")
async def dashboard_kpi():
    return {"success": True, "data": {
        "park_overview": {"total_enterprises": 12580, "growth_rate": "3.2%"},
        "investment": {"opportunities": 230, "conversion_rate": "5.2%"},
    }}


@router.get("/dashboard/overview")
async def dashboard_overview():
    """园区总览 — 供首页仪表盘使用"""
    return {"success": True, "data": {
        "park_overview": {"total_enterprises": 12580, "growth_rate": "3.2%"},
        "investment": {"opportunities": 230, "signed": 12, "conversion_rate": "5.2%"},
        "risk": {"high_risk": 20, "medium_risk": 80, "low_risk": 500},
        "ai_operations": {"agent_calls": 1520, "success_rate": "97.4%"},
    }}


@router.get("/dashboard/bi")
async def dashboard_bi():
    """BI 驾驶舱 — 全维度数据可视化"""
    return {"success": True, "data": {
        # === KPI 卡片 ===
        "kpi_cards": [
            {"key": "enterprises", "title": "园区企业总数", "value": 12580, "unit": "家",
             "trend": "+3.2%", "trend_up": True, "color": "#1677ff"},
            {"key": "investment", "title": "招商转化率", "value": 5.2, "unit": "%",
             "trend": "+0.8pp", "trend_up": True, "color": "#52c41a"},
            {"key": "risk", "title": "高风险企业", "value": 20, "unit": "家",
             "trend": "-5", "trend_up": False, "color": "#ff4d4f"},
            {"key": "ai_tasks", "title": "AI 调用次数", "value": 1520, "unit": "次/日",
             "trend": "+8%", "trend_up": True, "color": "#722ed1"},
        ],

        # === 产业分布 (柱状图数据) ===
        "industry_distribution": [
            {"name": "智能制造", "value": 3200, "pct": 25.4, "color": "#1677ff"},
            {"name": "机器人", "value": 2800, "pct": 22.3, "color": "#52c41a"},
            {"name": "新能源", "value": 2100, "pct": 16.7, "color": "#faad14"},
            {"name": "电子信息", "value": 1800, "pct": 14.3, "color": "#722ed1"},
            {"name": "生物医药", "value": 1500, "pct": 11.9, "color": "#13c2c2"},
            {"name": "新材料", "value": 1180, "pct": 9.4, "color": "#eb2f96"},
        ],

        # === 招商漏斗 ===
        "investment_funnel": [
            {"stage": "目标池", "count": 230, "color": "#1677ff"},
            {"stage": "初步接触", "count": 120, "color": "#52c41a"},
            {"stage": "深度洽谈", "count": 45, "color": "#faad14"},
            {"stage": "意向签约", "count": 18, "color": "#fa8c16"},
            {"stage": "正式入驻", "count": 12, "color": "#ff4d4f"},
        ],

        # === 风险趋势 (月度) ===
        "risk_trend": [
            {"month": "1月", "high": 35, "medium": 120, "low": 480},
            {"month": "2月", "high": 32, "medium": 115, "low": 490},
            {"month": "3月", "high": 28, "medium": 105, "low": 495},
            {"month": "4月", "high": 25, "medium": 98, "low": 500},
            {"month": "5月", "high": 22, "medium": 90, "low": 505},
            {"month": "6月", "high": 20, "medium": 80, "low": 500},
        ],

        # === AI 调用分布 ===
        "ai_usage": [
            {"agent": "招商智能体", "calls": 420, "pct": 27.6},
            {"agent": "风险雷达", "calls": 350, "pct": 23.0},
            {"agent": "政策顾问", "calls": 280, "pct": 18.4},
            {"agent": "产业研究", "calls": 220, "pct": 14.5},
            {"agent": "企业服务", "calls": 150, "pct": 9.9},
            {"agent": "BI 驾驶舱", "calls": 100, "pct": 6.6},
        ],

        # === AI 洞察 ===
        "insights": {
            "summary": "园区运营稳定，机器人产业热度持续上升，招商转化率稳步提升",
            "opportunities": [
                {"area": "核心零部件", "action": "重点关注伺服电机、减速器企业，补链强链"},
                {"area": "AI+制造", "action": "引入机器视觉、智能控制类企业，提升园区技术密度"},
            ],
            "alerts": [
                {"level": "warning", "msg": "2家企业融资动态异常，建议本周走访核实"},
                {"level": "info", "msg": "3条产业政策即将到期，12家符合条件的企业尽快申报"},
            ],
        },
    }}
