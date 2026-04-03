import json
import time
import re
import httpx
from app.config import settings

HEADERS = {
    "x-api-key": settings.API_KEY,
    "Content-Type": "application/json"
}


# Embeddings
def get_embedding(text: str) -> list[float]:
    response = httpx.post(
        f"{settings.EMBED_BASE_URL}/embeddings",
        headers=HEADERS,
        json={"model": settings.EMBEDDING_MODEL, "input": text},
        timeout=30.0
    )
    response.raise_for_status()
    data = response.json()
    if "data" in data:
        return data["data"][0]["embedding"]
    elif "embeddings" in data:
        return data["embeddings"][0]
    raise ValueError(f"Unexpected embedding response: {list(data.keys())}")


# Reranker
def rerank_texts(query: str, texts: list[str]) -> list[dict]:
    if not texts:
        return []
    response = httpx.post(
        f"{settings.RERANK_BASE_URL}/reranker",
        headers=HEADERS,
        json={
            "model": settings.RERANK_MODEL,
            "query": query,
            "texts": texts
        },
        timeout=30.0
    )
    response.raise_for_status()
    data = response.json()
    if "results" in data:
        results = data["results"]
    elif "scores" in data:
        results = [{"index": i, "score": s}
                   for i, s in enumerate(data["scores"])]
    else:
        results = [{"index": i, "score": 1.0} for i in range(len(texts))]
    return sorted(results, key=lambda x: x["score"], reverse=True)


def call_llm(
    messages: list[dict],
    tools: list[dict] = None,
    temperature: float = 0.3,
    max_tokens: int = 1024
) -> dict:
    payload = {
        "model": settings.MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    if tools:
        payload["tools"] = tools

    response = httpx.post(
        f"{settings.CHAT_BASE_URL}/chat/completions",
        headers=HEADERS,
        json=payload,
        timeout=60.0
    )
    response.raise_for_status()
    return response.json()


def compose_response(
    tool_results: list[tuple[str, dict]],
    lead_name: str,
    company: str
) -> str:
    """
    Builds a natural sales response directly from tool result dicts.
    No LLM call needed — deterministic, clean, never truncated.
    """
    parts = []
    first_name = lead_name.split()[0] if lead_name else "there"

    for tool_name, result in tool_results:

        if tool_name == "qualify_lead":
            score = result.get("lead_score", 0)
            tier = result.get("qualification_tier", "warm").upper()
            plan_hint = ""

            if score >= 75:
                opening = (
                    f"Hi {first_name}! Great to connect — based on what "
                    f"you've shared, you're an excellent fit for our platform. "
                )
            elif score >= 50:
                opening = (
                    f"Hi {first_name}! Thanks for reaching out. "
                    f"You sound like a solid candidate for what we offer. "
                )
            else:
                opening = (
                    f"Hi {first_name}! Thanks for getting in touch. "
                    f"I'd love to learn more about {company or 'your team'}. "
                )
            parts.append(opening)

        elif tool_name == "match_product":
            plan = result.get("recommended_plan", "Pro Plan")
            price = result.get("price", "")
            reason = result.get("reason", "")
            story = result.get("success_story", "")

            recommendation = (
                f"Based on your profile, I'd recommend our **{plan}** "
                f"({price}). {reason} "
            )
            parts.append(recommendation)

            # Add a snippet from the success story if available
            if story:
                # Extract just the first sentence of the story
                first_sentence = story.split('.')[0]
                if len(first_sentence) > 20:
                    parts.append(
                        f"Companies like yours have seen great results — "
                        f"{first_sentence.strip()}. "
                    )

        elif tool_name == "handle_objection":
            obj_type = result.get("objection_type", "general")

            # Speak naturally to the customer — don't leak the script
            objection_responses = {
                "price": (
                    f"I completely understand, {first_name} — "
                    f"$499/month is a big commitment for a 10-person team. "
                    f"The good news is you don't need Enterprise at all. "
                    f"Our Pro Plan at $99/month gives you everything a "
                    f"growing SaaS team needs — unlimited API calls, "
                    f"priority support, and all integrations. "
                    f"Most teams our size see ROI within the first month "
                    f"from time saved on manual work alone. "
                    f"Would you like to start with a 14-day free trial "
                    f"so you can show your board real numbers before committing?"
                ),
                "timing": (
                    f"Absolutely, {first_name} — take the time you need. "
                    f"To make your team's decision easier, I can set up "
                    f"a quick 20-minute demo with your key stakeholders "
                    f"this week and send over a comparison doc. "
                    f"Would that help move things forward?"
                ),
                "competitor": (
                    f"That's a fair point to raise, {first_name}. "
                    f"Where we stand out is reliability and support — "
                    f"our 99.9% uptime SLA and 4-hour response time "
                    f"means far less downtime cost for your team. "
                    f"Would a side-by-side comparison doc be helpful?"
                ),
                "security": (
                    f"Data security is our top priority, {first_name}. "
                    f"We're SOC2 Type II certified and fully GDPR compliant. "
                    f"I'd be happy to share our full security documentation "
                    f"or connect you with our security team directly."
                ),
                "implementation": (
                    f"Setup is much simpler than it looks, {first_name}. "
                    f"Our onboarding specialist handles the entire "
                    f"implementation for you — most teams go live in "
                    f"under 3 weeks with zero internal dev resources needed."
                ),
                "existing_solution": (
                    f"That makes sense, {first_name}. "
                    f"I'd love to understand what's working and what "
                    f"isn't with your current setup. "
                    f"Many teams switch to us because of gaps in "
                    f"reporting, API reliability, or support quality. "
                    f"Does any of that resonate?"
                ),
                "too_big": (
                    f"You're right — and that's exactly why we built "
                    f"our Starter Plan at $29/month for small teams. "
                    f"It covers everything you need to get started, "
                    f"and you only upgrade when your team grows. "
                    f"Want to kick things off with a free 14-day trial?"
                ),
                "general": (
                    f"I hear you, {first_name}. "
                    f"Let me address that concern directly — "
                    f"what specifically would need to be true for "
                    f"this to feel like the right fit for your team?"
                ),
            }
            parts.append(
                objection_responses.get(
                    obj_type,
                    objection_responses["general"]
                )
            )

        elif tool_name == "close_deal":
            plan = result.get("recommended_plan", "Pro Plan")
            urgency = result.get("urgency_trigger", "")
            next_step = result.get("next_step", "")
            converted = result.get("is_converted", False)

            if converted:
                parts.append(
                    f"Fantastic, {first_name} — let's get you started "
                    f"on the {plan}! "
                )
            else:
                parts.append(
                    f"Great choice, {first_name}! The {plan} is perfect "
                    f"for {company or 'your team'}. "
                )

            if urgency:
                parts.append(f"{urgency} ")
            if next_step:
                parts.append(f"{next_step} ")

            parts.append(
                f"You can sign up at app.platform.com/trial — "
                f"no credit card required, and your account is "
                f"live within minutes."
            )

    # Fallback if nothing was composed
    if not parts:
        return (
            f"Hi {first_name}! Thanks for reaching out. "
            f"I'd love to help {company or 'your team'} find the right "
            f"solution. Could you tell me more about your main requirements?"
        )

    return "".join(parts).strip()

def run_tool_loop(
    messages: list[dict],
    tools: list[dict],
    tool_executor,
    max_rounds: int = 5,
    lead_name: str = "",
    company: str = ""
) -> tuple[str, list[str], float]:
    """
    Runs the tool calling loop.
    Tool decisions made by usf1-mini.
    Final response composed deterministically from tool outputs.
    """
    start = time.time()
    agents_invoked = []
    current_messages = messages.copy()
    tool_results_collected = []   # list of (tool_name, result_dict)

    for round_num in range(max_rounds):
        response = call_llm(current_messages, tools)
        choice = response["choices"][0]
        finish_reason = choice["finish_reason"]
        message = choice["message"]
        content = message.get("content") or ""

        if finish_reason == "tool_calls":
            tool_calls = message.get("tool_calls", [])

            current_messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": tool_calls
            })

            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                try:
                    tool_args = json.loads(
                        tool_call["function"]["arguments"]
                    )
                except json.JSONDecodeError:
                    tool_args = {}

                agents_invoked.append(tool_name)
                tool_result_str = tool_executor(tool_name, tool_args)

                # Parse result for composition
                try:
                    tool_result_dict = json.loads(tool_result_str)
                except Exception:
                    tool_result_dict = {"summary": tool_result_str}

                tool_results_collected.append(
                    (tool_name, tool_result_dict)
                )

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", f"call_{round_num}"),
                    "name": tool_name,
                    "content": tool_result_str
                })

        elif finish_reason == "stop":
            # Model responded directly without tool call
            # Still compose from any collected tool results
            if tool_results_collected:
                break
            # If no tools were called and we have a clean response
            cleaned = content.strip()
            if cleaned and len(cleaned) > 40:
                total_latency = round(time.time() - start, 3)
                return cleaned, agents_invoked, total_latency
            break

        else:
            break

    if tool_results_collected:
        final_response = compose_response(
            tool_results_collected, lead_name, company
        )
    else:
        final_response = (
            f"Hi! Thanks for reaching out. I'd love to help "
            f"{company or 'your team'} find the right solution. "
            f"Could you tell me more about your requirements?"
        )

    total_latency = round(time.time() - start, 3)
    return final_response, agents_invoked, total_latency