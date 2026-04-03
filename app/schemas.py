from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

# Lead
class LeadCreate(BaseModel):
    name: str
    email: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    segment: Optional[str] = "smb"  # smb | mid_market | enterprise


class LeadOut(BaseModel):
    id: str
    name: str
    email: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    segment: str
    lead_score: int
    qualification_tier: str
    pipeline_stage: str
    recommended_plan: Optional[str]
    objections_raised: int
    objections_resolved: int
    is_converted: bool
    escalated_to_human: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Chat
class ChatRequest(BaseModel):
    lead_id: str
    message: str


class AgentInvocation(BaseModel):
    agent_name: str
    input_data: dict
    output_data: dict
    rag_hit: bool
    latency_seconds: float


class ChatResponse(BaseModel):
    session_id: str
    lead_id: str
    response: str
    agents_invoked: List[str]
    pipeline_stage: str
    lead_score: int
    rag_hits: int
    total_latency_seconds: float
    escalate_to_human: bool


# Pipeline
class PipelineState(BaseModel):
    lead_id: str
    name: str
    pipeline_stage: str
    qualification_tier: str
    lead_score: int
    budget_score: int
    authority_score: int
    need_score: int
    timeline_score: int
    recommended_plan: Optional[str]
    recommended_plan_reason: Optional[str]
    objections_raised: int
    objections_resolved: int
    is_converted: bool
    escalated_to_human: bool
    escalation_reason: Optional[str]
    total_sessions: int

    class Config:
        from_attributes = True


# Analytics
class ConversionAnalytics(BaseModel):
    total_leads: int
    qualified_leads: int
    converted_leads: int
    conversion_rate: float
    avg_lead_score: float
    avg_time_to_close_minutes: float
    escalation_rate: float
    objection_resolution_rate: float
    hot_leads: int
    warm_leads: int
    cold_leads: int
    stage_breakdown: dict
    top_recommended_plan: Optional[str]