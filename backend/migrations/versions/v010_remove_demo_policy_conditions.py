"""Remove legacy generic policy qualification templates.

Revision ID: 010_remove_demo_conditions
Revises: 009_business_indexes
"""

from typing import Union

from alembic import op


revision: str = "010_remove_demo_conditions"
down_revision: Union[str, None] = "009_business_indexes"
branch_labels = None
depends_on = None


_DEMO_PREDICATE = """
    conditions_reviewed_by IN ('template_suggestion', 'seed_policy_conditions')
    OR EXISTS (
        SELECT 1
        FROM jsonb_array_elements(COALESCE(eligibility_conditions, '[]'::jsonb)) AS item
        WHERE COALESCE(item->>'source_text', '') LIKE '%系统模板建议%'
           OR COALESCE(item->>'source_text', '') LIKE '%非政策原文%'
           OR COALESCE(item->>'source_text', '') LIKE '%通用示例规则%'
    )
"""


def upgrade() -> None:
    # Remove copied requirements first, while the owning policy still carries
    # the legacy origin marker used to identify the seeded records.
    op.execute(
        f"""
        UPDATE policy_chunks AS chunk
        SET metadata = COALESCE(chunk.metadata, '{{}}'::jsonb)
            - 'requirements'
            - 'conditions_reviewed_at'
            - 'conditions_reviewed_by'
        FROM policy AS policy
        WHERE chunk.policy_id = policy.policy_id
          AND ({_DEMO_PREDICATE})
        """
    )
    op.execute(
        f"""
        UPDATE policy
        SET eligibility_conditions = '[]'::jsonb,
            conditions_reviewed_at = NULL,
            conditions_reviewed_by = NULL
        WHERE {_DEMO_PREDICATE}
        """
    )


def downgrade() -> None:
    # Intentionally irreversible: fabricated eligibility rules must never be
    # recreated during rollback.
    pass
