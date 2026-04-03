import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime,
    Float, Integer, JSON, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Lead(Base):
    """
    Represents a sales prospect moving through the pipeline.
    """
    __tablename__ = "leads"

    id = Column(String, primary_key=True, default=gen_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Basic info
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True)
    company = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)

    # Customer segment for personalization
    # smb=small business | mid_market | enterprise
    segment = Column(String(50), default="smb")

    # BANT scores (set by Lead Qualification Agent)
    budget_score = Column(Integer, default=0)       # 0-25
    authority_score = Column(Integer, default=0)    # 0-25
    need_score = Column(Integer, default=0)         # 0-25
    timeline_score = Column(Integer, default=0)     # 0-25
    lead_score = Column(Integer, default=0)         # 0-100 total

    # Qualification result
    qualification_tier = Column(String(20), default="unqualified")
    # unqualified | cold | warm | hot

    # Pipeline stage tracking
    pipeline_stage = Column(String(50), default="new")
    # new → qualified → matched → objection_handled → closed → lost

    # Product recommendation (set by Product Matching Agent)
    recommended_plan = Column(String(100), nullable=True)
    recommended_plan_reason = Column(Text, nullable=True)

    # Objection tracking
    objections_raised = Column(Integer, default=0)
    objections_resolved = Column(Integer, default=0)

    # Closing
    is_converted = Column(Boolean, default=False)
    converted_at = Column(DateTime, nullable=True)
    time_to_close_minutes = Column(Float, nullable=True)

    # Escalated to human?
    escalated_to_human = Column(Boolean, default=False)
    escalation_reason = Column(Text, nullable=True)

    # Relationships
    sessions = relationship("SalesSession", back_populates="lead")


class SalesSession(Base):
    """
    A single conversation session with a lead.
    One lead can have multiple sessions.
    """
    __tablename__ = "sales_sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Full message history as JSON list
    # [{"role": "user"|"assistant"|"tool", "content": "..."}]
    messages = Column(JSON, default=list)

    # Which agents were invoked this session
    agents_invoked = Column(JSON, default=list)

    # Session-level metrics
    total_turns = Column(Integer, default=0)
    avg_latency = Column(Float, default=0.0)

    lead = relationship("Lead", back_populates="sessions")
    agent_logs = relationship("AgentLog", back_populates="session")


class AgentLog(Base):
    """
    Logs every individual agent tool call for transparency and debugging.
    """
    __tablename__ = "agent_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("sales_sessions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Which agent was called
    agent_name = Column(String(100), nullable=False)
    # qualify_lead | match_product | handle_objection | close_deal

    # What the agent received and returned
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)

    # RAG info
    rag_chunks_used = Column(JSON, nullable=True)
    rag_hit = Column(Boolean, default=False)

    # Performance
    latency_seconds = Column(Float, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    session = relationship("SalesSession", back_populates="agent_logs")