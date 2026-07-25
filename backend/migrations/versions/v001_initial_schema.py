"""Initial schema — all existing tables (P0-P4)

Revision ID: 001_initial
Revises: None
Create Date: 2026-07-25

Tables:
  — business: enterprise, enterprise_profile, industry, policy, policy_documents, policy_chunks, risk
  — runtime:  agent_task, agent_execution, agent_trace, agent_memory, conversation
  — rbac:     users, roles, permissions, user_roles, role_permissions
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ═══ Business Tables ═══
    op.create_table('industry',
        sa.Column('industry_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('industry.industry_id')),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(100)),
        sa.Column('description', sa.Text()),
        sa.Column('keywords', postgresql.ARRAY(sa.Text())),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('industry_id'),
    )

    op.create_table('enterprise',
        sa.Column('enterprise_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('credit_code', sa.String(50), unique=True),
        sa.Column('industry_id', sa.Integer(), sa.ForeignKey('industry.industry_id')),
        sa.Column('park_id', sa.String(50)),
        sa.Column('company_type', sa.String(50)),
        sa.Column('status', sa.String(30), default='active'),
        sa.Column('address', sa.Text()),
        sa.Column('description', sa.Text()),
        sa.Column('created_time', sa.DateTime()),
        sa.Column('updated_time', sa.DateTime()),
        sa.PrimaryKeyConstraint('enterprise_id'),
    )

    op.create_table('enterprise_profile',
        sa.Column('profile_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('enterprise_id', sa.String(50), sa.ForeignKey('enterprise.enterprise_id'), unique=True),
        sa.Column('business_scope', sa.Text()),
        sa.Column('core_product', sa.Text()),
        sa.Column('technology_stack', postgresql.JSONB()),
        sa.Column('customer_info', postgresql.JSONB()),
        sa.Column('funding_stage', sa.String(50)),
        sa.Column('employee_count', sa.Integer()),
        sa.Column('revenue_level', sa.String(50)),
        sa.Column('rd_ratio', sa.Float()),
        sa.Column('growth_rate', sa.Float()),
        sa.Column('ai_summary', sa.Text()),
        sa.Column('updated_time', sa.DateTime()),
        sa.PrimaryKeyConstraint('profile_id'),
    )

    op.create_table('policy',
        sa.Column('policy_id', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('level', sa.String(30)),
        sa.Column('department', sa.String(200)),
        sa.Column('category', sa.String(100)),
        sa.Column('industry_scope', postgresql.ARRAY(sa.Text())),
        sa.Column('region_scope', postgresql.ARRAY(sa.Text())),
        sa.Column('content', sa.Text()),
        sa.Column('publish_date', sa.Date()),
        sa.Column('expire_date', sa.Date()),
        sa.Column('status', sa.String(30), default='active'),
        sa.Column('source', sa.String(500)),
        sa.PrimaryKeyConstraint('policy_id'),
    )

    op.create_table('policy_documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('policy_id', sa.String(50), sa.ForeignKey('policy.policy_id')),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('file_format', sa.String(20)),
        sa.Column('file_hash', sa.String(64)),
        sa.Column('file_size', sa.Integer()),
        sa.Column('page_count', sa.Integer()),
        sa.Column('raw_text', sa.Text()),
        sa.Column('parse_status', sa.String(20), default='pending'),
        sa.Column('parse_error', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('policy_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chunk_id', sa.String(100), unique=True, nullable=False),
        sa.Column('policy_id', sa.String(50), sa.ForeignKey('policy.policy_id')),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('policy_documents.id')),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64)),
        sa.Column('token_count', sa.Integer()),
        sa.Column('metadata', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('risk',
        sa.Column('risk_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('enterprise_id', sa.String(50), sa.ForeignKey('enterprise.enterprise_id')),
        sa.Column('risk_type', sa.String(50)),
        sa.Column('risk_score', sa.Float()),
        sa.Column('risk_level', sa.String(20)),
        sa.Column('risk_reason', sa.Text()),
        sa.Column('source', sa.String(200)),
        sa.Column('indicators', postgresql.JSONB()),
        sa.Column('created_time', sa.DateTime()),
        sa.PrimaryKeyConstraint('risk_id'),
    )

    # ═══ Runtime Tables (P2) ═══
    op.create_table('conversation',
        sa.Column('conversation_id', sa.String(50), nullable=False),
        sa.Column('user_id', sa.String(50)),
        sa.Column('title', sa.String(500)),
        sa.Column('status', sa.String(30), default='active'),
        sa.Column('thread_id', sa.String(50)),
        sa.Column('message_count', sa.Integer(), default=0),
        sa.Column('last_message_at', sa.DateTime()),
        sa.Column('created_time', sa.DateTime()),
        sa.Column('updated_time', sa.DateTime()),
        sa.PrimaryKeyConstraint('conversation_id'),
    )

    op.create_table('agent_task',
        sa.Column('task_id', sa.String(50), nullable=False),
        sa.Column('conversation_id', sa.String(50)),
        sa.Column('user_id', sa.String(50)),
        sa.Column('intent', sa.String(100)),
        sa.Column('goal', sa.Text()),
        sa.Column('priority', sa.String(20)),
        sa.Column('plan', postgresql.JSONB()),
        sa.Column('status', sa.String(30), default='created'),
        sa.Column('result', postgresql.JSONB()),
        sa.Column('error', postgresql.JSONB()),
        sa.Column('created_time', sa.DateTime()),
        sa.Column('completed_time', sa.DateTime()),
        sa.PrimaryKeyConstraint('task_id'),
    )

    op.create_table('agent_execution',
        sa.Column('execution_id', sa.String(50), nullable=False),
        sa.Column('task_id', sa.String(50), sa.ForeignKey('agent_task.task_id')),
        sa.Column('agent_name', sa.String(100)),
        sa.Column('order_num', sa.Integer()),
        sa.Column('input', postgresql.JSONB()),
        sa.Column('output', postgresql.JSONB()),
        sa.Column('status', sa.String(30)),
        sa.Column('start_time', sa.DateTime()),
        sa.Column('end_time', sa.DateTime()),
        sa.Column('duration_ms', sa.Integer()),
        sa.Column('error', postgresql.JSONB()),
        sa.PrimaryKeyConstraint('execution_id'),
    )

    op.create_table('agent_trace',
        sa.Column('trace_id', sa.String(50), nullable=False),
        sa.Column('task_id', sa.String(50), sa.ForeignKey('agent_task.task_id')),
        sa.Column('step', sa.Integer()),
        sa.Column('type', sa.String(50)),
        sa.Column('agent_name', sa.String(100)),
        sa.Column('action', sa.String(200)),
        sa.Column('input', postgresql.JSONB()),
        sa.Column('output', postgresql.JSONB()),
        sa.Column('source', sa.String(200)),
        sa.Column('timestamp', sa.DateTime()),
        sa.Column('duration_ms', sa.Integer()),
        sa.PrimaryKeyConstraint('trace_id'),
    )

    op.create_table('agent_memory',
        sa.Column('memory_id', sa.String(50), nullable=False),
        sa.Column('conversation_id', sa.String(50), sa.ForeignKey('conversation.conversation_id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('memory_id'),
    )

    # ═══ RBAC Tables (P4) ═══
    op.create_table('users',
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('display_name', sa.String(200)),
        sa.Column('park_id', sa.String(50)),
        sa.Column('data_scope', sa.String(50), default='all'),  # P5: 数据隔离范围
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('user_id'),
    )

    op.create_table('roles',
        sa.Column('role_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(50), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100)),
        sa.Column('description', sa.Text()),
        sa.PrimaryKeyConstraint('role_id'),
    )

    op.create_table('permissions',
        sa.Column('permission_id', sa.String(50), nullable=False),
        sa.Column('code', sa.String(100), unique=True, nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_name', sa.String(200)),
        sa.Column('action', sa.String(50), default='execute'),
        sa.PrimaryKeyConstraint('permission_id'),
    )

    op.create_table('user_roles',
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('role_id', sa.String(50), sa.ForeignKey('roles.role_id'), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'role_id'),
    )

    op.create_table('role_permissions',
        sa.Column('role_id', sa.String(50), sa.ForeignKey('roles.role_id'), nullable=False),
        sa.Column('permission_id', sa.String(50), sa.ForeignKey('permissions.permission_id'), nullable=False),
        sa.PrimaryKeyConstraint('role_id', 'permission_id'),
    )


def downgrade() -> None:
    op.drop_table('role_permissions')
    op.drop_table('user_roles')
    op.drop_table('permissions')
    op.drop_table('roles')
    op.drop_table('users')
    op.drop_table('agent_memory')
    op.drop_table('agent_trace')
    op.drop_table('agent_execution')
    op.drop_table('agent_task')
    op.drop_table('conversation')
    op.drop_table('risk')
    op.drop_table('policy_chunks')
    op.drop_table('policy_documents')
    op.drop_table('policy')
    op.drop_table('enterprise_profile')
    op.drop_table('enterprise')
    op.drop_table('industry')
