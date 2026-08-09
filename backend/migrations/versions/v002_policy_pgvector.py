"""Add the missing pgvector column and indexes for policy retrieval.

Revision ID: 002_policy_pgvector
Revises: 001_initial
Create Date: 2026-07-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.database.vector_type import Vector


revision: str = "002_policy_pgvector"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "policy_chunks",
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_index(
        "idx_policy_documents_policy_filename",
        "policy_documents",
        ["policy_id", "filename"],
        unique=False,
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_policy_chunks_embedding_hnsw
        ON policy_chunks USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_policy_chunks_embedding_hnsw")
    op.drop_index(
        "idx_policy_documents_policy_filename",
        table_name="policy_documents",
    )
    op.drop_column("policy_chunks", "embedding")
