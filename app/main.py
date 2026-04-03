from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import engine, get_db, Base
from app.models import Lead, SalesSession, AgentLog
from app.schemas import (
    LeadCreate, LeadOut, ChatRequest, ChatResponse,
    PipelineState, ConversionAnalytics
)
from app.agents.orchestrator import run_sales_pipeline
from app.analytics import get_conversion_analytics

# Create all DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sales Agent System",
    description=(
        "Multi-agent sales pipeline using usf1-mini native tool calling. "
        "4 specialized agents: Lead Qualification, Product Matching, "
        "Objection Handling, and Deal Closing."
    ),
    version="1.0.0"
)



@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0", "agents": 4}


# Leads
@app.post("/leads", response_model=LeadOut, tags=["Leads"])
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    """Register a new sales prospect."""
    lead = Lead(
        name=payload.name,
        email=payload.email,
        company=payload.company,
        industry=payload.industry,
        segment=payload.segment or "smb"
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@app.get("/leads", response_model=List[LeadOut], tags=["Leads"])
def list_leads(
    stage: str = None,
    tier: str = None,
    db: Session = Depends(get_db)
):
    """List all leads with optional filters by stage or tier."""
    query = db.query(Lead)
    if stage:
        query = query.filter(Lead.pipeline_stage == stage)
    if tier:
        query = query.filter(Lead.qualification_tier == tier)
    return query.order_by(Lead.created_at.desc()).all()


@app.get("/leads/{lead_id}", response_model=LeadOut, tags=["Leads"])
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    """Get a single lead's details."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@app.get("/leads/{lead_id}/pipeline", response_model=PipelineState, tags=["Leads"])
def get_pipeline_state(lead_id: str, db: Session = Depends(get_db)):
    """Get the full pipeline state for a lead including all scores."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    session_count = db.query(SalesSession).filter(
        SalesSession.lead_id == lead_id
    ).count()

    return PipelineState(
        lead_id=lead.id,
        name=lead.name,
        pipeline_stage=lead.pipeline_stage,
        qualification_tier=lead.qualification_tier,
        lead_score=lead.lead_score,
        budget_score=lead.budget_score,
        authority_score=lead.authority_score,
        need_score=lead.need_score,
        timeline_score=lead.timeline_score,
        recommended_plan=lead.recommended_plan,
        recommended_plan_reason=lead.recommended_plan_reason,
        objections_raised=lead.objections_raised,
        objections_resolved=lead.objections_resolved,
        is_converted=lead.is_converted,
        escalated_to_human=lead.escalated_to_human,
        escalation_reason=lead.escalation_reason,
        total_sessions=session_count
    )


# Chat
@app.post("/leads/{lead_id}/chat", response_model=ChatResponse, tags=["Chat"])
def chat(
    lead_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Main sales conversation endpoint.
    The orchestrator routes the message to the appropriate agent(s)
    based on conversation context and pipeline stage.
    """
    # Validate lead
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Get or create active session
    session = db.query(SalesSession).filter(
        SalesSession.lead_id == lead_id
    ).order_by(SalesSession.created_at.desc()).first()

    if not session:
        session = SalesSession(lead_id=lead_id, messages=[])
        db.add(session)
        db.commit()
        db.refresh(session)

    # Run the multi-agent pipeline
    response_text, agents_invoked, rag_hits, total_latency = run_sales_pipeline(
        lead=lead,
        session=session,
        customer_message=payload.message,
        db=db
    )

    # Check escalation signals
    escalate = False
    message_lower = payload.message.lower()
    if any(w in message_lower for w in ["speak to human", "real person",
                                         "talk to someone", "call me",
                                         "escalate", "manager"]):
        escalate = True
        lead.escalated_to_human = True
        lead.escalation_reason = "Customer requested human agent"
        lead.pipeline_stage = "escalated"
        db.commit()

    return ChatResponse(
        session_id=session.id,
        lead_id=lead_id,
        response=response_text,
        agents_invoked=agents_invoked,
        pipeline_stage=lead.pipeline_stage,
        lead_score=lead.lead_score,
        rag_hits=rag_hits,
        total_latency_seconds=total_latency,
        escalate_to_human=escalate
    )


# Session History
@app.get("/leads/{lead_id}/sessions", tags=["Sessions"])
def get_sessions(lead_id: str, db: Session = Depends(get_db)):
    """Get all conversation sessions for a lead."""
    sessions = db.query(SalesSession).filter(
        SalesSession.lead_id == lead_id
    ).order_by(SalesSession.created_at.desc()).all()

    return [
        {
            "session_id": s.id,
            "created_at": s.created_at,
            "total_turns": s.total_turns,
            "agents_invoked": s.agents_invoked,
            "message_count": len(s.messages or [])
        }
        for s in sessions
    ]


@app.get("/leads/{lead_id}/sessions/{session_id}/logs", tags=["Sessions"])
def get_agent_logs(
    lead_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed agent invocation logs for a session."""
    logs = db.query(AgentLog).filter(
        AgentLog.session_id == session_id
    ).order_by(AgentLog.created_at).all()

    return [
        {
            "agent_name": log.agent_name,
            "input": log.input_data,
            "output": log.output_data,
            "rag_hit": log.rag_hit,
            "rag_chunks": log.rag_chunks_used,
            "latency_seconds": log.latency_seconds,
            "success": log.success,
            "created_at": log.created_at
        }
        for log in logs
    ]


# Analytics
@app.get("/analytics/conversion",
         response_model=ConversionAnalytics, tags=["Analytics"])
def conversion_analytics(db: Session = Depends(get_db)):
    """Platform-wide sales conversion funnel metrics."""
    return get_conversion_analytics(db)


@app.get("/analytics/leaderboard", tags=["Analytics"])
def leaderboard(db: Session = Depends(get_db)):
    """Top leads ranked by lead score."""
    leads = db.query(Lead).order_by(
        Lead.lead_score.desc()
    ).limit(10).all()

    return [
        {
            "rank": i + 1,
            "name": l.name,
            "company": l.company,
            "lead_score": l.lead_score,
            "tier": l.qualification_tier,
            "stage": l.pipeline_stage,
            "recommended_plan": l.recommended_plan,
            "is_converted": l.is_converted
        }
        for i, l in enumerate(leads)
    ]