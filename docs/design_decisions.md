# Design Decisions and Trade-offs

## 1. Native Tool Calling over External Agent Frameworks

**Decision:** Use USF1-MINI's native tool calling instead of 
Google ADK, LangGraph, or LlamaIndex.

**Reason:** The assessment provider supplies a tool calling endpoint 
that implements the OpenAI function calling spec. Using it directly:
- Eliminates external framework dependencies
- Uses the provider's own agent capability as intended
- Makes the LLM the actual decision-maker for agent routing
- Results in cleaner, more maintainable code

**Trade-off:** Less abstraction than a framework. Scaling to 20+ 
agents would benefit from a graph-based orchestrator like LangGraph.

---

## 2. Deterministic Response Composition

**Decision:** Build the final customer response from tool output 
data rather than asking the LLM to generate it.

**Reason:** USF1-MINI is a small model that exhibits two issues 
when asked to generate text after tool calls:
- Leaks internal reasoning (outputs JSON or tool names)
- Truncates responses mid-sentence

By composing responses deterministically from structured tool 
outputs, we guarantee complete, clean, personalized responses 
every time.

**Trade-off:** Responses follow templates rather than being 
fully generative. A larger model (GPT-4, Claude) would not 
need this approach.

---

## 3. Three Separate ChromaDB Collections

**Decision:** Products, success stories, and objections in 
separate collections rather than one combined KB.

**Reason:** Each agent has a distinct retrieval purpose. 
Mixing all documents in one collection introduces noise — 
a price objection query might retrieve product pricing 
instead of the objection response script.

**Trade-off:** More collections to manage. In production, 
metadata filtering on a single collection could achieve 
the same result.

---

## 4. BANT Scoring with Keyword Signals

**Decision:** Score BANT dimensions using keyword matching 
rather than LLM-based scoring.

**Reason:** Avoids an extra LLM call per qualification, 
reducing latency by ~15 seconds. Keyword signals for BANT 
dimensions are well-defined and predictable.

**Trade-off:** Less nuanced than LLM-based scoring. A 
customer who says "our investors just approved a $2M 
technology budget" scores the same as one who says 
"we have budget" — both trigger the keyword match.

---

## 5. SQLite over PostgreSQL

**Decision:** SQLite for persistence.

**Reason:** Zero setup for evaluators. Single file database, 
no server process. SQLAlchemy ORM abstracts the difference — 
switching to PostgreSQL requires only changing DATABASE_URL.

**Trade-off:** SQLite does not handle concurrent writes well. 
Not suitable for multi-worker production deployments.

---

## 6. Soft Pipeline Stages over Hard State Machine

**Decision:** Pipeline stage stored as a string field updated 
by each agent rather than a formal state machine.

**Reason:** Keeps the code simple and allows agents to update 
stage independently. The orchestrator does not enforce 
transition rules — the LLM decides which agent to call.

**Trade-off:** Possible inconsistencies (e.g., close_deal 
called before qualify_lead). A formal state machine would 
enforce valid transitions but adds complexity.

---

## 7. Session-based Conversation History

**Decision:** Store full message history as a JSON column 
on SalesSession rather than individual Message rows.

**Reason:** The entire history is always read and written 
together as a unit — denormalizing into JSON is more 
efficient than joining many rows.

**Trade-off:** Cannot query individual messages with SQL. 
For a production system with search requirements, 
individual Message rows would be better.

---

## Performance Analysis

### Observed latencies from testing
| Turn | Agents Invoked | Latency |
|---|---|---|
| 1 (intro + qualify + match) | 3 agents | 43s |
| 2 (security objection) | 1 agent | 21s |
| 3 (competitor objection) | 1 agent | 19s |
| 4 (implementation concern) | 1 agent | 22s |
| 5 (buying signal + close) | 1 agent | 18s |

### Latency breakdown per turn
| Stage | Time |
|---|---|
| usf-embed (query) | ~1-2s |
| ChromaDB retrieval | ~0.1s |
| usf-rerank | ~2-3s |
| usf1-mini tool call decision | ~10-15s |
| Response composition | ~0.01s |

The dominant cost is the LLM tool call decision step.

---

## Future Improvements

### Short term
- **Streaming responses** — SSE endpoint for real-time token delivery
- **Lead scoring history** — track score changes across sessions
- **Bulk lead import** — CSV upload for CRM migration
- **Webhook on conversion** — notify CRM when lead converts

### Medium term
- **Async tool execution** — run multiple tool calls in parallel
- **LLM-based BANT scoring** — more nuanced qualification
- **Email integration** — auto-send follow-up emails on stage change
- **A/B testing** — test different closing scripts against each other

### Long term
- **CRM integration** — sync with Salesforce/HubSpot
- **Voice interface** — real-time sales call assistant
- **Fine-tuned model** — train on successful conversion conversations
- **Multi-language support** — localized sales scripts per region