"""Seed DRAFT condition suggestions for policies that have no conditions.

Updates both Policy.eligibility_conditions and PolicyChunk.metadata_["requirements"]
so policy managers can review them. Templates never qualify an enterprise until
a human checks the policy text and changes a condition to REVIEWED.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text


CONDITION_TEMPLATES = [
    {
        "condition_code": "REGISTERED_REGION",
        "label": "注册地要求",
        "field": "region",
        "operator": "CONTAINS",
        "expected_value": ["广州"],
        "mandatory": True,
        "review_status": "DRAFT",
        "source_text": "系统模板建议（非政策原文）：请核对政策是否要求企业注册地在广州",
    },
    {
        "condition_code": "INDUSTRY_MATCH",
        "label": "产业方向匹配",
        "field": "industry",
        "operator": "CONTAINS",
        "expected_value": ["机器人", "智能制造", "高端装备"],
        "mandatory": True,
        "review_status": "DRAFT",
        "source_text": "系统模板建议（非政策原文）：请核对政策支持的产业方向",
    },
    {
        "condition_code": "ENTERPRISE_STATUS",
        "label": "经营状态正常",
        "field": "enterprise_status",
        "operator": "IN",
        "expected_value": ["存续", "在营", "正常"],
        "mandatory": True,
        "review_status": "DRAFT",
        "source_text": "系统模板建议（非政策原文）：请核对经营状态要求",
    },
    {
        "condition_code": "MIN_CAPITAL",
        "label": "注册资本要求",
        "field": "capital_amount",
        "operator": "GTE",
        "expected_value": 500,
        "mandatory": False,
        "review_status": "DRAFT",
        "source_text": "系统模板建议（非政策原文）：请核对是否存在注册资本门槛",
    },
    {
        "condition_code": "MIN_PATENTS",
        "label": "知识产权要求",
        "field": "patents_count",
        "operator": "GTE",
        "expected_value": 5,
        "mandatory": False,
        "review_status": "DRAFT",
        "source_text": "系统模板建议（非政策原文）：请核对是否存在知识产权门槛",
    },
]


async def seed() -> None:
    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://industrial:industrial@postgres:5432/industrial_park")
    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # Only add suggestions where no conditions have been prepared yet.
        result = await session.execute(
            text(
                "SELECT policy_id, title, industry_scope, region_scope FROM policy "
                "WHERE COALESCE(jsonb_array_length(eligibility_conditions), 0) = 0"
            )
        )
        rows = result.fetchall()
        print(f"Found {len(rows)} policies to update")

        updated_policies = 0
        updated_chunks = 0

        for row in rows:
            policy_id, title, industry_scope, region_scope = row

            # Tailor the industry condition based on the policy's scope
            conditions = []
            for tmpl in CONDITION_TEMPLATES:
                cond = dict(tmpl)  # copy
                if tmpl["condition_code"] == "INDUSTRY_MATCH" and industry_scope:
                    cond["expected_value"] = [
                        s.strip() for s in industry_scope[:3] if s and isinstance(s, str)
                    ] or tmpl["expected_value"]
                # REGISTERED_REGION always keeps hardcoded ["广州"] — enterprise locations
                # are district-level ("广州南沙") and need CONTAINS "广州", not "广州市"
                conditions.append(cond)

            # 2. Update policy row
            await session.execute(
                text(
                    "UPDATE policy SET eligibility_conditions = :conds, "
                    "conditions_reviewed_at = NULL, "
                    "conditions_reviewed_by = 'template_suggestion' "
                    "WHERE policy_id = :pid"
                ),
                {
                    "conds": __import__("json").dumps(conditions, ensure_ascii=False),
                    "pid": policy_id,
                },
            )
            updated_policies += 1

            # 3. Update all associated chunks metadata
            reqs_json = json.dumps(conditions, ensure_ascii=False)
            chunks_result = await session.execute(
                text(
                    "UPDATE policy_chunks "
                    "SET metadata = jsonb_set("
                    "  COALESCE(metadata, '{}'), "
                    "  '{requirements}', "
                    "  CAST(:reqs AS jsonb)"
                    ") "
                    "WHERE policy_id = :pid"
                ),
                {"reqs": reqs_json, "pid": policy_id},
            )
            updated_chunks += chunks_result.rowcount or 0

        await session.commit()
        print(f"Done: {updated_policies} policies + {updated_chunks} chunks updated")


if __name__ == "__main__":
    asyncio.run(seed())
