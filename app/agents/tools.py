"""
Agent Tool Functions
Each function = one specialized sales agent.
These are called by the orchestrator when usf1-mini decides to invoke a tool.
"""
import json
import time
from sqlalchemy.orm import Session
from app.rag import retrieve_and_rerank
from app.models import Lead, AgentLog


def _log_agent(
    db: Session,
    session_id: str,
    agent_name: str,
    input_data: dict,
    output_data: dict,
    rag_chunks: list,
    latency: float,
    success: bool = True,
    error: str = None
):
    """Persist an agent invocation log to the database."""
    log = AgentLog(
        session_id=session_id,
        agent_name=agent_name,
        input_data=input_data,
        output_data=output_data,
        rag_chunks_used=[c["metadata"] for c in rag_chunks] if rag_chunks else [],
        rag_hit=len(rag_chunks) > 0,
        latency_seconds=latency,
        success=success,
        error_message=error
    )
    db.add(log)
    db.commit()


# Tool 1: Lead Qualification Agent
def qualify_lead(
    lead: Lead,
    customer_message: str,
    db: Session,
    session_id: str
) -> dict:
    """
    Evaluates a prospect using the BANT framework.
    Scores Budget, Authority, Need, Timeline (0-25 each = 0-100 total).
    Updates the lead record with scores and qualification tier.

    Returns a dict with scores and qualification summary.
    """
    start = time.time()

    # RAG: retrieve qualification criteria and guidance
    rag_chunks = retrieve_and_rerank(
        collection_name="products",
        query=f"qualify lead {customer_message} {lead.industry or ''} {lead.segment}",
        n_results=5,
        top_k=2
    )
    rag_context = "\n".join([c["text"] for c in rag_chunks])

    # BANT scoring logic based on message signals
    message_lower = customer_message.lower()

    # Budget signals
    budget_score = 10  # default neutral
    if any(w in message_lower for w in ["budget", "afford", "cost", "price", "spend", "invest"]):
        if any(w in message_lower for w in ["no budget", "can't afford", "too expensive", "limited"]):
            budget_score = 5
        elif any(w in message_lower for w in ["enterprise", "large", "significant", "approved"]):
            budget_score = 25
        else:
            budget_score = 15

    # Segment-based budget adjustment
    if lead.segment == "enterprise":
        budget_score = min(25, budget_score + 10)
    elif lead.segment == "mid_market":
        budget_score = min(25, budget_score + 5)

    # Authority signals
    authority_score = 10  # default neutral
    if any(w in message_lower for w in ["ceo", "cto", "director", "vp", "head of", "owner", "founder", "decision"]):
        authority_score = 25
    elif any(w in message_lower for w in ["manager", "lead", "senior"]):
        authority_score = 18
    elif any(w in message_lower for w in ["team", "we", "our", "evaluating"]):
        authority_score = 12

    # Need signals
    need_score = 10  # default neutral
    if any(w in message_lower for w in ["need", "problem", "issue", "challenge", "struggling", "looking for", "require"]):
        need_score = 22
    elif any(w in message_lower for w in ["interested", "explore", "curious", "learn more"]):
        need_score = 15
    elif any(w in message_lower for w in ["just browsing", "no need", "not sure"]):
        need_score = 5

    # Timeline signals
    timeline_score = 10  # default neutral
    if any(w in message_lower for w in ["asap", "immediately", "urgent", "this month", "this week", "now"]):
        timeline_score = 25
    elif any(w in message_lower for w in ["quarter", "soon", "next month", "planning"]):
        timeline_score = 18
    elif any(w in message_lower for w in ["sometime", "eventually", "next year", "no rush"]):
        timeline_score = 5

    # Total lead score
    total_score = budget_score + authority_score + need_score + timeline_score

    # Qualification tier
    if total_score >= 75:
        tier = "hot"
    elif total_score >= 50:
        tier = "warm"
    elif total_score >= 25:
        tier = "cold"
    else:
        tier = "unqualified"

    # Update lead in DB
    lead.budget_score = budget_score
    lead.authority_score = authority_score
    lead.need_score = need_score
    lead.timeline_score = timeline_score
    lead.lead_score = total_score
    lead.qualification_tier = tier
    lead.pipeline_stage = "qualified"
    db.commit()

    result = {
        "lead_score": total_score,
        "qualification_tier": tier,
        "budget_score": budget_score,
        "authority_score": authority_score,
        "need_score": need_score,
        "timeline_score": timeline_score,
        "rag_context": rag_context,
        "summary": f"Lead scored {total_score}/100. Tier: {tier.upper()}. "
                   f"Budget={budget_score}/25, Authority={authority_score}/25, "
                   f"Need={need_score}/25, Timeline={timeline_score}/25."
    }

    _log_agent(
        db=db, session_id=session_id,
        agent_name="qualify_lead",
        input_data={"message": customer_message, "segment": lead.segment},
        output_data=result,
        rag_chunks=rag_chunks,
        latency=round(time.time() - start, 3)
    )

    return result


# Tool 2: Product Matching Agent
def match_product(
    lead: Lead,
    customer_message: str,
    db: Session,
    session_id: str
) -> dict:
    """
    Matches the lead's profile and needs to the best product plan.
    Retrieves relevant success stories for social proof.

    Returns recommended plan + reasoning + success story.
    """
    start = time.time()

    # RAG: find matching products
    product_chunks = retrieve_and_rerank(
        collection_name="products",
        query=f"{customer_message} {lead.segment} {lead.industry or ''} team size",
        n_results=5,
        top_k=2
    )

    # RAG: find relevant success stories by segment
    story_chunks = retrieve_and_rerank(
        collection_name="success_stories",
        query=f"{lead.segment} {lead.industry or ''} {customer_message}",
        n_results=5,
        top_k=2,
        where={"segment": lead.segment} if lead.segment != "smb" else None
    )

    all_rag_chunks = product_chunks + story_chunks
    product_context = "\n".join([c["text"] for c in product_chunks])
    story_context = "\n".join([c["text"] for c in story_chunks])

    # Recommend plan based on segment + lead score
    if lead.segment == "enterprise" or lead.lead_score >= 80:
        recommended = "Enterprise Plan"
        price = "$499+/month"
        reason = "Enterprise-grade requirements with compliance, SSO, and dedicated support needs."
    elif lead.segment == "mid_market" or lead.lead_score >= 60:
        recommended = "Mid-Market Plan"
        price = "$249/month"
        reason = "Growing team needs advanced user management and dedicated onboarding support."
    elif lead.lead_score >= 40:
        recommended = "Pro Plan"
        price = "$99/month"
        reason = "SMB with clear needs — Pro Plan's unlimited API calls and priority support fit well."
    else:
        recommended = "Starter Plan"
        price = "$29/month"
        reason = "Early-stage evaluation — Starter Plan lets you prove value before committing."

    # Update lead record
    lead.recommended_plan = recommended
    lead.recommended_plan_reason = reason
    lead.pipeline_stage = "matched"
    db.commit()

    result = {
        "recommended_plan": recommended,
        "price": price,
        "reason": reason,
        "product_details": product_context,
        "success_story": story_context,
        "summary": f"Recommended {recommended} at {price}. {reason}"
    }

    _log_agent(
        db=db, session_id=session_id,
        agent_name="match_product",
        input_data={"message": customer_message, "segment": lead.segment,
                    "lead_score": lead.lead_score},
        output_data=result,
        rag_chunks=all_rag_chunks,
        latency=round(time.time() - start, 3)
    )

    return result


# Tool 3: Objection Handling Agent
def handle_objection(
    lead: Lead,
    customer_message: str,
    db: Session,
    session_id: str
) -> dict:
    """
    Detects the type of objection and retrieves the best response script.
    Tracks objection counts on the lead record.

    Returns objection type + response strategy + success story for proof.
    """
    start = time.time()

    # RAG: find matching objection response
    objection_chunks = retrieve_and_rerank(
        collection_name="objections",
        query=customer_message,
        n_results=5,
        top_k=2
    )

    # RAG: find supporting success story
    story_chunks = retrieve_and_rerank(
        collection_name="success_stories",
        query=f"{customer_message} {lead.segment}",
        n_results=3,
        top_k=1
    )

    all_rag_chunks = objection_chunks + story_chunks

    # Detect objection type from message
    message_lower = customer_message.lower()
    if any(w in message_lower for w in ["expensive", "price", "cost", "budget", "afford", "cheap"]):
        objection_type = "price"
    elif any(w in message_lower for w in ["think", "later", "not now", "decide", "team", "discuss"]):
        objection_type = "timing"
    elif any(w in message_lower for w in ["competitor", "alternative", "other", "vs", "compare"]):
        objection_type = "competitor"
    elif any(w in message_lower for w in ["already", "existing", "current", "using", "have"]):
        objection_type = "existing_solution"
    elif any(w in message_lower for w in ["security", "data", "privacy", "compliance", "gdpr", "safe"]):
        objection_type = "security"
    elif any(w in message_lower for w in ["complex", "technical", "implement", "integrate", "setup"]):
        objection_type = "implementation"
    elif any(w in message_lower for w in ["small", "tiny", "just me", "solo", "overkill"]):
        objection_type = "too_big"
    else:
        objection_type = "general"

    # Update lead objection counts
    lead.objections_raised = (lead.objections_raised or 0) + 1
    lead.objections_resolved = (lead.objections_resolved or 0) + 1
    lead.pipeline_stage = "objection_handled"

    # If price objection on Enterprise — downgrade recommendation to Pro
    if objection_type == "price" and lead.recommended_plan == "Enterprise Plan":
        lead.recommended_plan = "Pro Plan"
        lead.recommended_plan_reason = (
            "Downgraded from Enterprise after price objection. "
            "Pro Plan better fits team size and budget."
        )

    # If too_big objection — downgrade to Starter
    if objection_type == "too_big" and lead.recommended_plan in [
        "Enterprise Plan", "Mid-Market Plan", "Pro Plan"
    ]:
        lead.recommended_plan = "Starter Plan"
        lead.recommended_plan_reason = (
            "Downgraded to Starter after customer indicated team is small."
        )

    db.commit()

    objection_scripts = "\n".join([c["text"] for c in objection_chunks])
    success_story = "\n".join([c["text"] for c in story_chunks])

    result = {
        "objection_type": objection_type,
        "response_scripts": objection_scripts,
        "supporting_story": success_story,
        "objections_raised": lead.objections_raised,
        "summary": f"Detected '{objection_type}' objection. "
                   f"Retrieved response scripts and supporting social proof."
    }

    _log_agent(
        db=db, session_id=session_id,
        agent_name="handle_objection",
        input_data={"message": customer_message, "objection_type": objection_type},
        output_data=result,
        rag_chunks=all_rag_chunks,
        latency=round(time.time() - start, 3)
    )

    return result


# Tool 4: Deal Closing Agent
def close_deal(
    lead: Lead,
    customer_message: str,
    db: Session,
    session_id: str
) -> dict:
    """
    Guides the customer toward conversion.
    Generates a personalized closing strategy based on lead profile.
    Marks the lead as converted if closing signals are strong.

    Returns closing strategy + next steps + urgency triggers.
    """
    start = time.time()
    from datetime import datetime

    # RAG: get plan details for closing pitch
    product_chunks = retrieve_and_rerank(
        collection_name="products",
        query=f"{lead.recommended_plan or ''} features benefits trial",
        n_results=3,
        top_k=2
    )

    # RAG: get success story for final social proof
    story_chunks = retrieve_and_rerank(
        collection_name="success_stories",
        query=f"{lead.segment} {lead.industry or ''} results ROI",
        n_results=3,
        top_k=1
    )

    all_rag_chunks = product_chunks + story_chunks

    # Detect buying signals
    message_lower = customer_message.lower()
    buying_signals = any(w in message_lower for w in [
        "ready", "let's go", "sign up", "start", "proceed", "yes",
        "how do i", "next steps", "trial", "sounds good", "interested"
    ])

    # Build closing strategy based on tier
    tier = lead.qualification_tier
    plan = lead.recommended_plan or "Pro Plan"

    if tier == "hot":
        urgency = "Limited-time offer: 3 months free on annual billing (offer ends this week)."
        next_step = "Start your free trial now — no credit card required. I'll send the onboarding guide immediately."
    elif tier == "warm":
        urgency = "Annual billing saves you 20% — lock in current pricing before our next review."
        next_step = "Start with our 14-day free trial to experience the full Pro feature set risk-free."
    else:
        urgency = "Our Starter Plan is free to try for 14 days — zero commitment."
        next_step = "Let's start you on the free trial so you can experience the value firsthand."

    # Mark as converted if strong buying signals
    if buying_signals and tier in ["hot", "warm"]:
        lead.is_converted = True
        lead.converted_at = datetime.utcnow()
        if lead.created_at:
            delta = datetime.utcnow() - lead.created_at
            lead.time_to_close_minutes = round(delta.total_seconds() / 60, 2)
        lead.pipeline_stage = "closed"
    else:
        lead.pipeline_stage = "closing"

    db.commit()

    product_details = "\n".join([c["text"] for c in product_chunks])
    story = "\n".join([c["text"] for c in story_chunks])

    result = {
        "recommended_plan": plan,
        "urgency_trigger": urgency,
        "next_step": next_step,
        "buying_signals_detected": buying_signals,
        "is_converted": lead.is_converted,
        "product_details": product_details,
        "success_story": story,
        "summary": f"Closing strategy for {tier.upper()} lead. "
                   f"Plan: {plan}. Converted: {lead.is_converted}."
    }

    _log_agent(
        db=db, session_id=session_id,
        agent_name="close_deal",
        input_data={"message": customer_message, "tier": tier, "plan": plan},
        output_data=result,
        rag_chunks=all_rag_chunks,
        latency=round(time.time() - start, 3)
    )

    return result


# Maps tool names (as defined in the LLM tool spec) to their functions
TOOL_FUNCTIONS = {
    "qualify_lead": qualify_lead,
    "match_product": match_product,
    "handle_objection": handle_objection,
    "close_deal": close_deal
}