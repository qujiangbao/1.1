"""PolicyMockData — 开发/演示环境的政策数据

从 gateway.py _mock_policy_search() 迁移。
保证 POLICY_RAG_MODE=mock 时行为与 v1.1 100% 一致。
"""
from __future__ import annotations

from typing import List, Optional
from datetime import datetime


class PolicyMockData:
    """v1.1 8 条预设政策 — Mock 模式数据源"""

    _POLICIES: List[dict] = [
        {
            "policy_id": "POL-001",
            "title": "广东省机器人产业集群行动计划(2024-2027)",
            "level": "provincial",
            "department": "广东省工信厅",
            "summary": "重点支持工业机器人、服务机器人、特种机器人三大方向，对入驻产业园企业给予最高500万元补贴",
            "keywords": ["机器人", "产业", "集群", "补贴"],
            "region": "广东省",
            "publish_date": "2024-01-15",
            "expire_date": "2027-12-31",
        },
        {
            "policy_id": "POL-002",
            "title": "广州市人工智能产业扶持办法",
            "level": "municipal",
            "department": "广州市科技局",
            "summary": "对AI+制造融合项目给予研发费用50%补贴，最高300万元",
            "keywords": ["人工智能", "AI", "制造", "研发", "补贴"],
            "region": "广州市",
            "publish_date": "2024-03-20",
            "expire_date": "2026-12-31",
        },
        {
            "policy_id": "POL-003",
            "title": "十四五机器人产业发展规划",
            "level": "national",
            "department": "工信部",
            "summary": "到2025年机器人产业营业收入年均增速超过20%，建成3-5个国际影响力产业集群",
            "keywords": ["机器人", "产业", "规划", "十四五"],
            "region": "全国",
            "publish_date": "2021-12-01",
            "expire_date": "2025-12-31",
        },
        {
            "policy_id": "POL-004",
            "title": "广州市黄埔区促进智能制造发展办法",
            "level": "district",
            "department": "黄埔区工信局",
            "summary": "对新入驻智能制造企业给予三年租金补贴，前两年免租",
            "keywords": ["智能制造", "租金", "补贴", "入驻"],
            "region": "广州市黄埔区",
            "publish_date": "2024-06-01",
            "expire_date": "2027-05-31",
        },
        {
            "policy_id": "POL-005",
            "title": "广东省战略性产业集群重点产业链「链主」企业遴选",
            "level": "provincial",
            "department": "广东省发改委",
            "summary": "评选机器人产业链链主企业，给予税收优惠和用地优先权",
            "keywords": ["链主", "产业链", "机器人", "税收", "用地"],
            "region": "广东省",
            "publish_date": "2024-02-10",
            "expire_date": None,
        },
        {
            "policy_id": "POL-006",
            "title": "广州市科技型中小企业技术创新基金",
            "level": "municipal",
            "department": "广州市科技局",
            "summary": "对机器人领域科技型中小企业提供50-200万元创新基金",
            "keywords": ["科技型", "中小企业", "创新", "基金", "机器人"],
            "region": "广州市",
            "publish_date": "2024-04-15",
            "expire_date": "2026-04-14",
        },
        {
            "policy_id": "POL-007",
            "title": "关于加快培育发展制造业优质企业的指导意见",
            "level": "national",
            "department": "工信部",
            "summary": "培育一批机器人领域专精特新「小巨人」企业",
            "keywords": ["制造业", "优质企业", "专精特新", "小巨人", "机器人"],
            "region": "全国",
            "publish_date": "2023-08-20",
            "expire_date": None,
        },
        {
            "policy_id": "POL-008",
            "title": "广东省制造业数字化转型实施方案",
            "level": "provincial",
            "department": "广东省政府",
            "summary": "推动制造业智能化改造，对机器人应用示范项目给予30%设备补贴",
            "keywords": ["数字化转型", "制造业", "智能化", "机器人", "设备补贴"],
            "region": "广东省",
            "publish_date": "2024-05-01",
            "expire_date": "2027-04-30",
        },
    ]

    @classmethod
    def search(
        cls,
        query: str = "",
        filters: Optional[dict] = None,
        top_k: int = 10,
    ) -> List[dict]:
        """搜索政策 — 与 v1.1 逻辑完全一致"""
        results = list(cls._POLICIES)

        # 关键词过滤
        if query:
            q = query.lower()
            filtered = [p for p in results
                        if q in p["title"].lower() or q in p["summary"].lower()
                        or any(q in kw.lower() for kw in p.get("keywords", []))]
            if filtered:
                results = filtered
            # else: 无匹配时返回全部（v1.1 行为）

        # 级别过滤
        if filters and filters.get("level"):
            lv = filters["level"]
            results = [p for p in results if p["level"] == lv]

        # 地区过滤
        if filters and filters.get("region"):
            region = str(filters["region"]).lower()
            results = [p for p in results
                       if region in p.get("region", "").lower() or region in p.get("title", "").lower()]

        # 行业过滤
        if filters and filters.get("industry"):
            ind = str(filters["industry"]).lower()
            results = [p for p in results
                       if ind in " ".join(p.get("keywords", [])).lower() or ind in p.get("title", "").lower()]

        # 活跃过滤
        if filters and filters.get("active_only") is not False:
            results = [p for p in results if p.get("expire_date") is None or p["expire_date"] >= "2026-01-01"]

        # 构造 chunk 格式 — 与 v1.1 ToolGateway 返回格式一致
        chunks = []
        for i, p in enumerate(results[:top_k]):
            chunks.append({
                "chunk_id": f"{p['policy_id']}-c000",
                "policy_id": p["policy_id"],
                "chunk_index": 0,
                "content": p["summary"],
                "score": round(0.95 - (i * 0.03), 2),  # 模拟相似度
                "search_method": "mock",
                "metadata": {
                    "title": p["title"],
                    "level": p["level"],
                    "department": p["department"],
                    "region": p.get("region", ""),
                    "publish_date": p.get("publish_date"),
                    "expire_date": p.get("expire_date"),
                    "keywords": p.get("keywords", []),
                },
                "evidence": [{
                    "type": "mock_preset",
                    "value": f"预设政策 #{i+1}",
                    "url": "",
                }],
            })

        return chunks

    @classmethod
    def get_policy_by_id(cls, policy_id: str) -> Optional[dict]:
        """按 ID 获取单条政策"""
        for p in cls._POLICIES:
            if p["policy_id"] == policy_id:
                return p
        return None

    @classmethod
    def get_all_policies(cls) -> List[dict]:
        return list(cls._POLICIES)
