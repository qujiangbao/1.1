"""Enterprise models — 对应 Database_Physical_Schema_V1.0"""
from sqlalchemy import Column, String, Integer, Float, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from app.database.vector_type import Vector
from app.database.session import Base
from datetime import datetime


class Enterprise(Base):
    __tablename__ = "enterprise"

    enterprise_id = Column(String(50), primary_key=True)
    name = Column(String(500), nullable=False)
    credit_code = Column(String(50), unique=True)
    industry_id = Column(Integer, ForeignKey("industry.industry_id"))
    park_id = Column(String(50))
    company_type = Column(String(50))
    status = Column(String(30), default="active")
    address = Column(Text)
    description = Column(Text)
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow)


class EnterpriseProfile(Base):
    __tablename__ = "enterprise_profile"

    profile_id = Column(Integer, primary_key=True, autoincrement=True)
    enterprise_id = Column(String(50), ForeignKey("enterprise.enterprise_id"), unique=True)
    business_scope = Column(Text)
    core_product = Column(Text)
    technology_stack = Column(JSONB)
    customer_info = Column(JSONB)
    funding_stage = Column(String(50))
    employee_count = Column(Integer)
    revenue_level = Column(String(50))
    rd_ratio = Column(Float)
    growth_rate = Column(Float)
    ai_summary = Column(Text)
    updated_time = Column(DateTime, default=datetime.utcnow)


class Industry(Base):
    __tablename__ = "industry"

    industry_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    parent_id = Column(Integer, ForeignKey("industry.industry_id"), nullable=True)
    level = Column(Integer, nullable=False)
    category = Column(String(100))
    description = Column(Text)
    keywords = Column(ARRAY(Text))
    is_active = Column(Boolean, default=True)


class Policy(Base):
    __tablename__ = "policy"

    policy_id = Column(String(50), primary_key=True)
    title = Column(String(500), nullable=False)
    level = Column(String(30))
    department = Column(String(200))
    category = Column(String(100))
    industry_scope = Column(ARRAY(Text))
    region_scope = Column(ARRAY(Text))
    content = Column(Text)
    publish_date = Column(Date)
    expire_date = Column(Date)
    status = Column(String(30), default="active")
    source = Column(String(500))
    eligibility_conditions = Column(JSONB, nullable=False, default=list)
    conditions_reviewed_at = Column(DateTime)
    conditions_reviewed_by = Column(String(50))


class PolicyDocument(Base):
    """P1: 原始政策文档"""
    __tablename__ = "policy_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_id = Column(String(50), ForeignKey("policy.policy_id"), nullable=True)
    filename = Column(String(500), nullable=False)
    file_format = Column(String(20))
    file_hash = Column(String(64))
    file_size = Column(Integer)
    page_count = Column(Integer)
    raw_text = Column(Text)
    parse_status = Column(String(20), default="pending")
    parse_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PolicyChunk(Base):
    """P1: 政策分块 + pgvector 向量"""
    __tablename__ = "policy_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(String(100), unique=True, nullable=False)
    policy_id = Column(String(50), ForeignKey("policy.policy_id"), nullable=True)
    document_id = Column(Integer, ForeignKey("policy_documents.id"), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64))
    token_count = Column(Integer)
    embedding = Column(Vector(1536))
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class Risk(Base):
    __tablename__ = "risk"

    risk_id = Column(Integer, primary_key=True, autoincrement=True)
    enterprise_id = Column(String(50), ForeignKey("enterprise.enterprise_id"))
    risk_type = Column(String(50))
    risk_score = Column(Float)
    risk_level = Column(String(20))
    risk_reason = Column(Text)
    source = Column(String(200))
    indicators = Column(JSONB)
    created_time = Column(DateTime, default=datetime.utcnow)
