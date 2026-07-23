"""Agent runtime models"""
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
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


class Conversation(Base):
    __tablename__ = "conversation"

    conversation_id = Column(String(50), primary_key=True)
    user_id = Column(String(50))
    title = Column(String(500))
    status = Column(String(30), default="active")
    created_time = Column(DateTime, default=datetime.utcnow)
