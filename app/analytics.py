from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Lead, SalesSession, AgentLog
from app.schemas import ConversionAnalytics


def get_conversion_analytics(db: Session) -> ConversionAnalytics:
    """Compute platform-wide sales conversion metrics."""

    all_leads = db.query(Lead).all()
    total_leads = len(all_leads)

    if total_leads == 0:
        return ConversionAnalytics(
            total_leads=0, qualified_leads=0, converted_leads=0,
            conversion_rate=0.0, avg_lead_score=0.0,
            avg_time_to_close_minutes=0.0, escalation_rate=0.0,
            objection_resolution_rate=0.0, hot_leads=0,
            warm_leads=0, cold_leads=0, stage_breakdown={},
            top_recommended_plan=None
        )

    # Qualification counts
    qualified = [l for l in all_leads if l.pipeline_stage != "new"]
    converted = [l for l in all_leads if l.is_converted]
    escalated = [l for l in all_leads if l.escalated_to_human]

    # Tier breakdown
    hot = sum(1 for l in all_leads if l.qualification_tier == "hot")
    warm = sum(1 for l in all_leads if l.qualification_tier == "warm")
    cold = sum(1 for l in all_leads if l.qualification_tier == "cold")

    # Avg lead score
    avg_score = round(
        sum(l.lead_score for l in all_leads) / total_leads, 1
    )

    # Avg time to close
    closed_with_time = [
        l.time_to_close_minutes for l in converted
        if l.time_to_close_minutes is not None
    ]
    avg_time_to_close = round(
        sum(closed_with_time) / len(closed_with_time), 2
    ) if closed_with_time else 0.0

    # Objection resolution rate
    total_raised = sum(l.objections_raised or 0 for l in all_leads)
    total_resolved = sum(l.objections_resolved or 0 for l in all_leads)
    obj_resolution_rate = round(
        total_resolved / total_raised, 2
    ) if total_raised > 0 else 0.0

    # Stage breakdown
    stage_counts = {}
    for lead in all_leads:
        stage = lead.pipeline_stage or "new"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    # Most recommended plan
    plans = [l.recommended_plan for l in all_leads if l.recommended_plan]
    top_plan = max(set(plans), key=plans.count) if plans else None

    return ConversionAnalytics(
        total_leads=total_leads,
        qualified_leads=len(qualified),
        converted_leads=len(converted),
        conversion_rate=round(len(converted) / total_leads, 2),
        avg_lead_score=avg_score,
        avg_time_to_close_minutes=avg_time_to_close,
        escalation_rate=round(len(escalated) / total_leads, 2),
        objection_resolution_rate=obj_resolution_rate,
        hot_leads=hot,
        warm_leads=warm,
        cold_leads=cold,
        stage_breakdown=stage_counts,
        top_recommended_plan=top_plan
    )