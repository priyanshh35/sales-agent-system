# Agent Roles and Sales Workflow

## Overview

The system implements four specialized AI agents, each responsible for 
a distinct stage of the sales pipeline. Agents are defined as tool 
functions and invoked autonomously by the USF1-MINI orchestrator based 
on conversation context.

---

## Agent 1 — Lead Qualification Agent

**Tool name:** `qualify_lead`
**Pipeline stage:** `new → qualified`

### Responsibility
Evaluates incoming prospects using the BANT framework to determine 
whether they are worth pursuing and how urgently.

### BANT Scoring
Each dimension scored 0-25, total 0-100:

| Dimension | Signals | Max Score |
|---|---|---|
| **Budget** | Mentions approved budget, enterprise segment, spending intent | 25 |
| **Authority** | Job title (CTO, CEO, Director), decision-making language | 25 |
| **Need** | Problem statements, urgency words, specific requirements | 25 |
| **Timeline** | "This quarter", "ASAP", "urgently", specific deadlines | 25 |

### Qualification Tiers
| Score | Tier | Action |
|---|---|---|
| 75-100 | 🔴 Hot | Immediate follow-up, fast-track to closing |
| 50-74 | 🟡 Warm | Nurture with product demo and case studies |
| 25-49 | 🔵 Cold | Long-term nurture, educational content |
| 0-24 | ⚪ Unqualified | Deprioritize |

### RAG Usage
Retrieves product catalog to understand what questions to ask 
based on segment and industry context.

---

## Agent 2 — Product Matching Agent

**Tool name:** `match_product`
**Pipeline stage:** `qualified → matched`

### Responsibility
Maps the qualified lead's profile, segment, and needs to the most 
appropriate product plan. Retrieves relevant customer success stories 
for social proof.

### Matching Logic
| Condition | Recommended Plan |
|---|---|
| Segment = enterprise OR score ≥ 80 | Enterprise Plan ($499+/month) |
| Segment = mid_market OR score ≥ 60 | Mid-Market Plan ($249/month) |
| Score ≥ 40 | Pro Plan ($99/month) |
| Score < 40 | Starter Plan ($29/month) |

### RAG Usage
- Queries `products` collection for plan features matching customer needs
- Queries `success_stories` collection filtered by segment for social proof

### Plan Adjustment
Recommended plan is dynamically updated if objections arise:
- Price objection on Enterprise → downgrades to Pro Plan
- Too-big objection → downgrades to Starter Plan

---

## Agent 3 — Objection Handling Agent

**Tool name:** `handle_objection`
**Pipeline stage:** `matched → objection_handled`

### Responsibility
Detects the type of objection from the customer message and retrieves 
the appropriate response script. Tracks objection counts for analytics.

### Objection Types Handled
| Type | Trigger Keywords | Response Strategy |
|---|---|---|
| `price` | expensive, cost, budget, afford, justify | ROI reframe, plan downgrade, free trial |
| `security` | SOC2, GDPR, breach, compliance, encryption | Credentials, certifications, on-premise option |
| `competitor` | competitor, cheaper, same features, why choose | Differentiate on uptime, support, SLA |
| `timing` | think about it, not now, discuss with team | Create urgency, offer demo, schedule follow-up |
| `implementation` | complex, IT team, legacy, deployment | Onboarding specialist, 3-week timeline |
| `existing_solution` | already use, currently have | Identify gaps, offer comparison |
| `too_big` | small team, overkill, just us | Right-size to Starter Plan |

### RAG Usage
- Queries `objections` collection for matching response scripts
- Queries `success_stories` for supporting social proof

---

## Agent 4 — Deal Closing Agent

**Tool name:** `close_deal`
**Pipeline stage:** `objection_handled → closed`

### Responsibility
Guides the customer toward conversion using urgency triggers and 
personalized closing strategies. Marks lead as converted when 
strong buying signals are detected.

### Buying Signal Detection
Triggers closing when message contains:
`ready, let's go, sign up, start, proceed, yes, how do I, 
next steps, trial, sounds good, interested`

### Closing Strategy by Tier
| Tier | Urgency Trigger | Next Step |
|---|---|---|
| Hot | 3 months free on annual (limited time) | Start free trial immediately |
| Warm | 20% off annual billing | 14-day free trial |
| Cold | Zero-commitment trial | Starter Plan free trial |

### Conversion Tracking
When buying signals detected + tier is hot/warm:
- Sets `is_converted = True`
- Records `converted_at` timestamp
- Calculates `time_to_close_minutes` from lead creation

---

## Agent Coordination Flow
New Message Arrives
│
▼
USF1-MINI reads message + pipeline state
│
├── New lead? ──────────────────→ qualify_lead
│                                      │
│                                      ▼
│                               match_product
│
├── Objection detected? ────────→ handle_objection
│
├── Buying signal? ─────────────→ close_deal
│
└── Multiple signals? ──────────→ Chain multiple agents

### Multi-Agent Chaining Example
When a new enterprise lead introduces themselves with budget and 
urgency signals, the orchestrator chains all three agents in one turn:
`qualify_lead → match_product → close_deal`

---

## Human Escalation

The system automatically escalates to human agents when:
- Customer explicitly requests: "speak to a human", "call me", "manager"
- Sets `escalated_to_human = True` on the lead record
- Sets `pipeline_stage = "escalated"`
- Records `escalation_reason`

Human agents can review full session history and agent logs via:
`GET /leads/{id}/sessions/{sid}/logs`