# RAG Implementation for Sales Knowledge

## Overview

The sales agent system uses a three-stage RAG pipeline across three 
specialized knowledge bases. Each agent queries the most relevant 
collection for its task, ensuring grounded, factual responses.

---

## RAG Pipeline
Customer Message
│
▼
[usf-embed] → query vector (1536 dimensions)
│
▼
[ChromaDB]  → cosine similarity → top 5 candidates
│
▼
[usf-rerank] → neural relevance scoring → top 3 chunks
│
▼
Agent tool function uses chunks in logic + response

---

## Three Knowledge Bases

### 1. Products Collection (6 documents)
**Purpose:** Plan features, pricing, and positioning  
**Used by:** qualify_lead, match_product, close_deal

| Document | Content |
|---|---|
| Starter Plan | $29/mo, 3 users, 1000 API calls, basic analytics |
| Pro Plan | $99/mo, 20 users, unlimited API, priority support |
| Mid-Market Plan | $249/mo, 100 users, dedicated onboarding |
| Enterprise Plan | $499+/mo, unlimited users, SSO, compliance |
| Pro Add-on | AI Insights Module $49/mo extra |
| All Plans | Common features, trial terms, guarantees |

### 2. Success Stories Collection (6 documents)
**Purpose:** Social proof by segment and industry  
**Used by:** match_product, handle_objection, close_deal

| Document | Company | Segment | Outcome |
|---|---|---|---|
| TechFlow | SaaS startup | SMB | 4x ROI, upgraded Starter→Pro |
| RetailMax | E-commerce | Mid-Market | -40% support tickets |
| GlobalBank | Finance | Enterprise | $2.3M saved annually |
| HealthPlus | Healthcare | SMB | Zero findings on security audit |
| AgencyHub | Marketing | SMB | +35% revenue per employee |
| LogiCorp | Logistics | Mid-Market | Fastest implementation in vendor history |

### 3. Objections Collection (7 documents)
**Purpose:** Objection → response scripts  
**Used by:** handle_objection

| Document | Objection Type | Key Response |
|---|---|---|
| obj_001 | Price | ROI reframe, cost-per-outcome |
| obj_002 | Timing | Urgency creation, demo offer |
| obj_003 | Competitor | Differentiate on reliability + SLA |
| obj_004 | Existing solution | Gap identification |
| obj_005 | Security | SOC2, GDPR, on-premise option |
| obj_006 | Implementation | Onboarding specialist, 3-week timeline |
| obj_007 | Too big | Right-size to Starter Plan |

---

## Retrieval Strategy Per Agent

### qualify_lead
Collection: products
Query: "{message} {segment} {industry}"
Purpose: Understand which plan tier fits the customer's context

### match_product
Collection 1: products
Query: "{message} {segment} {industry} team size"
Top-k: 2 product chunks
Collection 2: success_stories
Query: "{segment} {industry} {message}"
Filter: segment = lead.segment (for enterprise/mid_market)
Top-k: 2 story chunks

### handle_objection
Collection 1: objections
Query: customer_message verbatim
Top-k: 2 objection scripts
Collection 2: success_stories
Query: "{message} {segment}"
Top-k: 1 supporting story

### close_deal
Collection 1: products
Query: "{recommended_plan} features benefits trial"
Top-k: 2 plan details
Collection 2: success_stories
Query: "{segment} {industry} results ROI"
Top-k: 1 success story

---

## Reranking

After vector retrieval returns top-5 candidates, the `usf-rerank` 
model scores each candidate for true relevance to the query.

### Why Reranking Matters
Vector similarity measures geometric distance between embeddings — 
it finds *related* content but not always the most *relevant* content.

Example for security objection:
Vector similarity scores:     Reranker scores:
security doc   → 0.82         security doc    → 0.95 ✓
timing script  → 0.71         timing script   → 0.31
price script   → 0.65         price script    → 0.18

The reranker correctly promotes the security document even when 
vector distances are close.

---

## Knowledge Base Design Decisions

### Why synthetic/seeded data?
No domain data was provided with the assessment. The seed script 
generates a representative B2B SaaS sales knowledge base covering 
the most common sales scenarios. In production, this would be 
replaced by actual product documentation, CRM data, and real 
customer case studies.

### Why three separate collections?
Separating products, stories, and objections allows agents to query 
only the relevant collection for their task — reducing noise in 
retrieval and improving precision.

### Idempotent seeding
The seed script checks existing document IDs before inserting. 
Running it multiple times never creates duplicates.

---

## RAG Quality Metrics

Tracked automatically via `AgentLog` records:

| Metric | Description |
|---|---|
| `rag_hit` | Whether any chunks were retrieved for a tool call |
| `rag_chunks_used` | Metadata of retrieved chunks (category, plan, segment) |
| `rag_hits` (per turn) | Cumulative RAG hits across all agent calls in session |