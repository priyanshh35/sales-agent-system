"""
Sales Pipeline Orchestrator

Defines the 4 agent tools for usf1-mini and manages the full
tool calling loop. The LLM autonomously decides which agent to
invoke based on the conversation context.
"""
import json
from sqlalchemy.orm import Session
from app.models import Lead, SalesSession
from app.llm import run_tool_loop
from app.agents.tools import TOOL_FUNCTIONS


SALES_TOOLS = [
    {
        "name": "qualify_lead",
        "description": (
            "Evaluates a sales prospect using the BANT framework "
            "(Budget, Authority, Need, Timeline). Call this FIRST when "
            "a new customer introduces themselves or describes their situation. "
            "Scores the lead 0-100 and assigns a tier: hot, warm, or cold. "
            "Always call this before any other agent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_message": {
                    "type": "string",
                    "description": "The customer's message describing their situation or needs"
                },
                "reason": {
                    "type": "string",
                    "description": "Why you are qualifying this lead now"
                }
            },
            "required": ["customer_message"]
        }
    },
    {
        "name": "match_product",
        "description": (
            "Identifies the best product plan for a qualified lead based on "
            "their needs, company size, and segment. Call this AFTER "
            "qualify_lead returns a score. Retrieves relevant product details "
            "and customer success stories for personalized recommendations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_message": {
                    "type": "string",
                    "description": "The customer's message about their requirements"
                },
                "reason": {
                    "type": "string",
                    "description": "Why this product match is being made"
                }
            },
            "required": ["customer_message"]
        }
    },
    {
        "name": "handle_objection",
        "description": (
            "Addresses customer objections, hesitations, or concerns such as "
            "price ('too expensive'), timing ('need to think'), competitors "
            "('X is cheaper'), security ('is our data safe?'), or complexity "
            "('seems hard to implement'). Call this when the customer expresses "
            "ANY doubt, hesitation, or pushback. Retrieves proven response "
            "scripts and supporting success stories."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_message": {
                    "type": "string",
                    "description": "The customer's objection or concern verbatim"
                },
                "objection_type": {
                    "type": "string",
                    "description": "Category: price | timing | competitor | security | implementation | existing_solution | general"
                }
            },
            "required": ["customer_message"]
        }
    },
    {
        "name": "close_deal",
        "description": (
            "Guides the customer toward conversion and closing the sale. "
            "Call this when the customer shows buying signals such as asking "
            "about next steps, pricing details, trial signup, or saying they "
            "are ready to proceed. Also call this after objections have been "
            "resolved and the conversation is moving positively. Generates "
            "urgency triggers and personalized closing strategies."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_message": {
                    "type": "string",
                    "description": "The customer's message showing interest in proceeding"
                },
                "reason": {
                    "type": "string",
                    "description": "Why you are initiating the closing sequence"
                }
            },
            "required": ["customer_message"]
        }
    }
]


def build_system_prompt(lead: Lead) -> str:
    """Build a concise system prompt for the sales orchestrator."""

    segment_context = {
        "smb": "small business",
        "mid_market": "mid-market company",
        "enterprise": "large enterprise"
    }.get(lead.segment, "business")

    return (
        f"You are a sales AI assistant. "
        f"You are talking to {lead.name} from {lead.company or 'their company'}, "
        f"a {segment_context} in the {lead.industry or 'technology'} industry.\n\n"
        f"Current pipeline stage: {lead.pipeline_stage}\n"
        f"Lead score: {lead.lead_score}/100\n"
        f"Recommended plan: {lead.recommended_plan or 'not yet determined'}\n\n"
        f"Use your tools to analyze the customer message. "
        f"Call qualify_lead first for new leads. "
        f"Call match_product after qualification. "
        f"Call handle_objection when customer hesitates. "
        f"Call close_deal when customer shows buying interest.\n\n"
        f"IMPORTANT: After calling tools, you will be asked to write "
        f"a response. Always write in plain English. Never output JSON."
    )

def run_sales_pipeline(
    lead: Lead,
    session: SalesSession,
    customer_message: str,
    db: Session
) -> tuple[str, list[str], int, float]:
    """
    Main entry point. Runs the full tool calling loop for one conversation turn.

    Flow:
      1. Build personalized system prompt
      2. Load session history
      3. Add current user message
      4. Send to usf1-mini with all 4 tools defined
      5. LLM decides which tool(s) to call
      6. Execute tool functions locally
      7. Return result to LLM for final response
      8. Persist everything

    Returns:
      (response_text, agents_invoked, rag_hits, total_latency)
    """

    # 1. Build messages
    system_prompt = build_system_prompt(lead)
    messages = [{"role": "system", "content": system_prompt}]

    # 2. Load conversation history from session
    history = session.messages or []
    messages.extend(history)

    # 3. Add current user message
    messages.append({"role": "user", "content": customer_message})

    # 4. Define tool executor — closure over lead/session/db
    def tool_executor(tool_name: str, tool_args: dict) -> str:
        """Called by run_tool_loop when the LLM requests a tool."""
        tool_fn = TOOL_FUNCTIONS.get(tool_name)
        if not tool_fn:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            # All tools receive lead, message, db, session_id
            result = tool_fn(
                lead=lead,
                customer_message=tool_args.get("customer_message", customer_message),
                db=db,
                session_id=session.id
            )
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e), "tool": tool_name})

    # 5. Run the tool calling loop
    response_text, agents_invoked, total_latency = run_tool_loop(
        messages=messages,
        tools=SALES_TOOLS,
        tool_executor=tool_executor,
        max_rounds=6,
        lead_name=lead.name,
        company=lead.company or ""
    )

    # 6. Count RAG hits from agent logs this session
    from app.models import AgentLog
    logs = db.query(AgentLog).filter(
        AgentLog.session_id == session.id
    ).all()
    rag_hits = sum(1 for log in logs if log.rag_hit)

    # 7. Update session history
    updated_messages = history.copy()
    updated_messages.append({"role": "user", "content": customer_message})
    updated_messages.append({"role": "assistant", "content": response_text})

    session.messages = updated_messages
    session.agents_invoked = list(set(
        (session.agents_invoked or []) + agents_invoked
    ))
    session.total_turns = (session.total_turns or 0) + 1
    db.commit()

    return response_text, agents_invoked, rag_hits, total_latency