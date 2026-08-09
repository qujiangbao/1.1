"""Downgrade legacy global policy templates from REVIEWED to DRAFT.

The historical seed copied five generic conditions to every policy and marked
them reviewed. That can create false enterprise-eligibility conclusions. This
repair is deliberately scoped to rows created by that seed marker.
"""
from __future__ import annotations

import asyncio
import json
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def to_draft(conditions: list[dict]) -> list[dict]:
    repaired = []
    for raw in conditions:
        condition = dict(raw)
        condition["review_status"] = "DRAFT"
        source = str(condition.get("source_text") or "").strip()
        if not source.startswith("系统模板建议（非政策原文）"):
            condition["source_text"] = (
                f"系统模板建议（非政策原文）：{source}" if source
                else "系统模板建议（非政策原文）：请对照政策正文核验"
            )
        repaired.append(condition)
    return repaired


async def repair() -> None:
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://industrial:industrial@postgres:5432/industrial_park",
    )
    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT policy_id, eligibility_conditions FROM policy "
                    "WHERE conditions_reviewed_by = 'seed_policy_conditions'"
                )
            )
        ).mappings().all()
        updated_chunks = 0
        for row in rows:
            repaired = to_draft(list(row["eligibility_conditions"] or []))
            payload = json.dumps(repaired, ensure_ascii=False)
            await session.execute(
                text(
                    "UPDATE policy SET eligibility_conditions = CAST(:conditions AS jsonb), "
                    "conditions_reviewed_at = NULL, "
                    "conditions_reviewed_by = 'template_suggestion' "
                    "WHERE policy_id = :policy_id"
                ),
                {"conditions": payload, "policy_id": row["policy_id"]},
            )
            result = await session.execute(
                text(
                    "UPDATE policy_chunks SET metadata = jsonb_set("
                    "COALESCE(metadata, '{}'), '{requirements}', CAST(:conditions AS jsonb)) "
                    "WHERE policy_id = :policy_id"
                ),
                {"conditions": payload, "policy_id": row["policy_id"]},
            )
            updated_chunks += result.rowcount or 0
        await session.commit()
        print(f"REPAIRED_POLICIES={len(rows)} REPAIRED_CHUNKS={updated_chunks}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(repair())
