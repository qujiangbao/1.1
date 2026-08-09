"""Agent runtime models"""
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from app.database.session import Base
from datetime import datetime


class AgentTask(Base):
    __tablename__ = "agent_task"

    task_id = Column(String(50), primary_key=True)
    conversation_id = Column(String(50))
    user_id = Column(String(50))
    intent = Column(String(100))
    goal = Column(Text)
    priority = Column(String(20))
    plan = Column(JSONB)
    status = Column(String(30), default="created")
    result = Column(JSONB)
    error = Column(JSONB)
    created_time = Column(DateTime, default=datetime.utcnow)
    completed_time = Column(DateTime)


class AgentExecution(Base):
    __tablename__ = "agent_execution"

    execution_id = Column(String(50), primary_key=True)
    task_id = Column(String(50), ForeignKey("agent_task.task_id"))
    agent_name = Column(String(100))
    order_num = Column(Integer)
    input = Column(JSONB)
    output = Column(JSONB)
    status = Column(String(30))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_ms = Column(Integer)
    error = Column(JSONB)


class AgentTrace(Base):
    __tablename__ = "agent_trace"

    trace_id = Column(String(50), primary_key=True)
    task_id = Column(String(50), ForeignKey("agent_task.task_id"))
    step = Column(Integer)
    type = Column(String(50))
    agent_name = Column(String(100))
    action = Column(String(200))
    input = Column(JSONB)
    output = Column(JSONB)
    source = Column(String(200))
    timestamp = Column(DateTime, default=datetime.utcnow)
    duration_ms = Column(Integer)


class AgentMemory(Base):
    """P2: Agent 对话记忆 — 持久化多轮对话上下文"""
    __tablename__ = "agent_memory"

    memory_id = Column(String(50), primary_key=True)
    conversation_id = Column(String(50), ForeignKey("conversation.conversation_id"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversation"

    conversation_id = Column(String(50), primary_key=True)
    user_id = Column(String(50))
    title = Column(String(500))
    status = Column(String(30), default="active")
    # P2: Checkpointer + Memory 集成
    thread_id = Column(String(50), nullable=True)        # LangGraph thread_id
    message_count = Column(Integer, default=0)            # 消息计数
    last_message_at = Column(DateTime, nullable=True)     # 最后消息时间
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
