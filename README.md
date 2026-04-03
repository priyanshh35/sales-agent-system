# Sales Agent System

A multi-agent AI sales pipeline built with FastAPI and USF1-MINI native 
tool calling. Four specialized agents collaborate autonomously to qualify 
leads, match products, handle objections, and close deals — all powered 
by Retrieval Augmented Generation (RAG).

---

## Architecture
Customer Message
│
▼
┌─────────────────────────────────────┐
│         USF1-MINI Orchestrator      │
│         (Native Tool Calling)       │
│                                     │
│  ┌─────────────────────────────┐    │
│  │   qualify_lead tool         │    │
│  │   match_product tool        │    │
│  │   handle_objection tool     │    │
│  │   close_deal tool           │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
│
▼
Tool executes (Python + RAG)
│
▼
Structured response composed

The LLM autonomously decides which agent tool(s) to invoke based on 
conversation context — achieving true agentic behavior without any 
external orchestration framework.

---

## Features

- **Lead Qualification Agent** — BANT scoring (Budget, Authority, Need, Timeline) 0-100
- **Product Matching Agent** — maps lead profile to best plan with success stories
- **Objection Handling Agent** — detects and addresses 7 objection types with RAG scripts
- **Deal Closing Agent** — urgency triggers, personalized closing, conversion tracking
- **RAG Pipeline** — usf-embed + ChromaDB + usf-rerank across 3 knowledge bases
- **Full pipeline state tracking** — stage, scores, objection counts, conversion time
- **Analytics endpoint** — conversion funnel metrics across all leads
- **Agent logs** — every tool invocation logged with inputs, outputs, RAG hits

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| Agent Orchestration | USF1-MINI native tool calling |
| LLM | usf1-mini |
| Embeddings | usf-embed |
| Reranker | usf-rerank |
| Vector Database | ChromaDB |
| Relational Database | SQLite + SQLAlchemy |
| Validation | Pydantic v2 |
| HTTP Client | httpx |

---

## Project Structure
sales-agent-system/
├── app/
│   ├── main.py                 # FastAPI routes
│   ├── config.py               # Environment settings
│   ├── database.py             # SQLAlchemy engine + session
│   ├── models.py               # Lead, SalesSession, AgentLog tables
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── llm.py                  # Tool calling loop + response composer
│   ├── rag.py                  # ChromaDB retrieval pipeline
│   ├── analytics.py            # Conversion metrics
│   └── agents/
│       ├── tools.py            # 4 agent tool functions
│       └── orchestrator.py     # Tool definitions + pipeline runner
├── docs/
│   ├── api_documentation.md
│   ├── agent_roles.md
│   ├── rag_implementation.md
│   ├── design_decisions.md
│   └── example_conversations.md
├── seed_knowledge_base.py      # Populates 3 ChromaDB collections
├── requirements.txt
├── .env.example
└── README.md

---

## Installation

### Prerequisites
- Python 3.10+
- pip
- Git

### 1. Clone the repository
```bash
git clone https://github.com/priyanshh35/sales-agent-system.git
cd sales-agent-system
```

### 2. Create virtual environment
```bash
# Mac/Linux
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:
```env
API_KEY=your_api_key_here

CHAT_BASE_URL=https://api.us.inc/usf/v1/hiring
EMBED_BASE_URL=https://api.us.inc/usf/v1/hiring/embed
RERANK_BASE_URL=https://api.us.inc/usf/v1/hiring/embed

MODEL_NAME=usf1-mini
EMBEDDING_MODEL=usf-embed
RERANK_MODEL=usf-rerank

DATABASE_URL=sqlite:///./sales.db
CHROMA_DB_PATH=./chroma_db
```

### 5. Seed the knowledge base
```bash
python seed_knowledge_base.py
```

Expected output:
🌱 Seeding sales knowledge bases...
✅ 'products' already seeded (6 docs)
✅ 'success_stories' already seeded (6 docs)
✅ 'objections' already seeded (7 docs)
🎉 All knowledge bases seeded successfully!

### 6. Start the server
```bash
uvicorn app.main:app --reload --port 8001
```

### 7. Open Swagger UI
Navigate to: **http://localhost:8001/docs**

---

## Quick Start — Example Flow

### 1. Create a lead
```bash
curl -X POST http://localhost:8001/leads \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sarah Chen",
    "email": "sarah@techflow.io",
    "company": "TechFlow",
    "industry": "saas",
    "segment": "smb"
  }'
```

### 2. Start the conversation
```bash
curl -X POST http://localhost:8001/leads/{lead_id}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "<lead_id>",
    "message": "Hi, I am the founder of a 10-person SaaS startup. We urgently need a platform to automate customer onboarding and have budget approved this quarter."
  }'
```

### 3. Check pipeline state
```bash
curl http://localhost:8001/leads/{lead_id}/pipeline
```

### 4. View analytics
```bash
curl http://localhost:8001/analytics/conversion
```

---

## API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/leads` | Create new lead |
| GET | `/leads` | List all leads with filters |
| GET | `/leads/{id}` | Get lead details |
| GET | `/leads/{id}/pipeline` | Full pipeline state + BANT scores |
| POST | `/leads/{id}/chat` | Send message — auto-routes to agents |
| GET | `/leads/{id}/sessions` | List conversation sessions |
| GET | `/leads/{id}/sessions/{sid}/logs` | Agent invocation logs |
| GET | `/analytics/conversion` | Conversion funnel metrics |
| GET | `/analytics/leaderboard` | Top leads by score |

---

## Knowledge Base

| Collection | Documents | Content |
|---|---|---|
| `products` | 6 docs | Starter, Pro, Mid-Market, Enterprise plans + features |
| `success_stories` | 6 docs | Customer case studies by segment and industry |
| `objections` | 7 docs | Objection → response scripts for 7 objection types |
