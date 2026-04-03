"""
Populates ChromaDB with 3 knowledge bases:
  1. products        — plan details, pricing, features
  2. success_stories — customer case studies by segment
  3. objections      — objection → response scripts

Run once: python seed_knowledge_base.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from app.rag import add_documents, get_collection


# 1. Product Catalog
PRODUCTS = [
    {
        "id": "prod_001",
        "text": "Starter Plan: $29/month. Up to 3 users, 1000 API calls/month, email support, basic analytics dashboard, CSV export. Best for freelancers and early-stage startups testing the platform.",
        "metadata": {"collection": "products", "plan": "starter", "price": "29", "segment": "smb"}
    },
    {
        "id": "prod_002",
        "text": "Pro Plan: $99/month. Up to 20 users, unlimited API calls, priority support with 4-hour SLA, advanced analytics, custom integrations, webhook support, data export in all formats. Best for growing SMBs and teams that need reliability.",
        "metadata": {"collection": "products", "plan": "pro", "price": "99", "segment": "smb"}
    },
    {
        "id": "prod_003",
        "text": "Enterprise Plan: Custom pricing starting at $499/month. Unlimited users, dedicated account manager, 99.99% uptime SLA, SSO/SAML authentication, on-premise deployment option, custom contract terms, compliance reports (SOC2, GDPR). Best for large organizations with complex requirements.",
        "metadata": {"collection": "products", "plan": "enterprise", "price": "499+", "segment": "enterprise"}
    },
    {
        "id": "prod_004",
        "text": "Pro Plan add-on: AI Insights Module at $49/month extra. Includes predictive analytics, automated report generation, anomaly detection, and natural language querying of your data. Available on Pro and Enterprise plans only.",
        "metadata": {"collection": "products", "plan": "pro_addon", "price": "49", "segment": "smb"}
    },
    {
        "id": "prod_005",
        "text": "All plans include: 14-day free trial with no credit card required, 99.9% uptime guarantee, daily backups, SSL encryption, GDPR compliance, and access to our documentation and community forum.",
        "metadata": {"collection": "products", "plan": "all", "segment": "all"}
    },
    {
        "id": "prod_006",
        "text": "Mid-Market Plan: $249/month. Up to 100 users, unlimited API calls, dedicated onboarding specialist, 2-hour support SLA, advanced role-based access control, audit logs, and multi-workspace support. Best for companies with 50-500 employees.",
        "metadata": {"collection": "products", "plan": "mid_market", "price": "249", "segment": "mid_market"}
    },
]

# 2. Customer Success Stories
SUCCESS_STORIES = [
    {
        "id": "story_001",
        "text": "TechFlow (SaaS startup, 8 employees) started on Starter Plan. Within 3 months they automated their entire customer onboarding workflow, reducing manual work by 70%. Upgraded to Pro after seeing 4x ROI. Quote: 'We paid for the annual Pro plan with the savings from our first month alone.'",
        "metadata": {"collection": "success_stories", "segment": "smb", "plan": "starter_to_pro", "industry": "saas"}
    },
    {
        "id": "story_002",
        "text": "RetailMax (e-commerce, 200 employees) moved from a competitor to our Mid-Market Plan. Integrated with their Shopify store in 2 days using webhooks. Reduced support tickets by 40% and improved customer satisfaction score from 72 to 91 in 6 months.",
        "metadata": {"collection": "success_stories", "segment": "mid_market", "plan": "mid_market", "industry": "ecommerce"}
    },
    {
        "id": "story_003",
        "text": "GlobalBank (financial services, 5000 employees) chose Enterprise Plan for its SOC2 compliance and on-premise deployment. Deployed across 12 departments in 8 weeks. Saved $2.3M annually by replacing 4 legacy tools. Compliance audit passed first try.",
        "metadata": {"collection": "success_stories", "segment": "enterprise", "plan": "enterprise", "industry": "finance"}
    },
    {
        "id": "story_004",
        "text": "HealthPlus (healthcare startup, 25 employees) was concerned about GDPR and data privacy. Chose Pro Plan for its encryption and compliance features. Passed their first external security audit with zero findings. Now processing 50,000 patient records monthly.",
        "metadata": {"collection": "success_stories", "segment": "smb", "plan": "pro", "industry": "healthcare"}
    },
    {
        "id": "story_005",
        "text": "AgencyHub (marketing agency, 45 employees) manages 30+ client accounts on a single Pro Plan workspace. Uses the API to build custom dashboards for each client. Revenue per employee increased by 35% after switching from manual reporting.",
        "metadata": {"collection": "success_stories", "segment": "smb", "plan": "pro", "industry": "agency"}
    },
    {
        "id": "story_006",
        "text": "LogiCorp (logistics, 800 employees) evaluated 5 vendors before choosing Mid-Market Plan. Key factors: webhook reliability, API rate limits, and dedicated onboarding. Went live in 3 weeks — fastest implementation in their vendor history.",
        "metadata": {"collection": "success_stories", "segment": "mid_market", "plan": "mid_market", "industry": "logistics"}
    },
]

# 3. Objection → Response Scripts
OBJECTIONS = [
    {
        "id": "obj_001",
        "text": "Objection: 'It's too expensive' or 'The price is too high' or 'We don't have budget'. Response: Reframe around ROI rather than cost. Ask: 'What does your current solution cost, including staff time?' Present cost-per-outcome: 'Our Pro Plan at $99/month typically saves teams 10+ hours/week — at average salaries that's $2000+/month in savings.' Offer annual billing for 20% discount. Mention 14-day free trial to prove value before committing.",
        "metadata": {"collection": "objections", "objection_type": "price", "tier": "all"}
    },
    {
        "id": "obj_002",
        "text": "Objection: 'We need to think about it' or 'Let me discuss with the team' or 'Not right now'. Response: This signals unresolved concerns. Ask: 'What specific questions would help your team decide?' Offer to join a call with decision makers. Create urgency: 'Our current pricing locks in at renewal — we have a promotion ending this Friday for 3 months free on annual plans.' Schedule a specific follow-up time rather than leaving it open.",
        "metadata": {"collection": "objections", "objection_type": "timing", "tier": "all"}
    },
    {
        "id": "obj_003",
        "text": "Objection: 'Your competitor is cheaper' or 'Company X offers the same for less'. Response: Never badmouth competitors. Instead differentiate on value: 'You're right that some tools are cheaper — the difference is in reliability and support. Our 99.9% uptime SLA and 4-hour support response means downtime costs you less.' Ask what specific features they're comparing. Often cheaper tools lack webhooks, advanced analytics, or compliance features that create hidden costs.",
        "metadata": {"collection": "objections", "objection_type": "competitor", "tier": "all"}
    },
    {
        "id": "obj_004",
        "text": "Objection: 'We already have a solution' or 'We use X and it works fine'. Response: Acknowledge their current setup. Ask: 'What would need to be true for you to consider switching?' Identify pain points: 'Many teams using X come to us specifically because of [limitation]. Does that resonate?' Offer a side-by-side comparison doc. Emphasize free migration support on Pro and above.",
        "metadata": {"collection": "objections", "objection_type": "existing_solution", "tier": "all"}
    },
    {
        "id": "obj_005",
        "text": "Objection: 'We're worried about data security' or 'Is our data safe?' or 'We have compliance requirements'. Response: Lead with credentials: 'We're SOC2 Type II certified and GDPR compliant.' For Enterprise: offer on-premise deployment. Share the HealthPlus case study (healthcare company that passed security audit with zero findings). Offer to connect them with our security team for a technical deep-dive call.",
        "metadata": {"collection": "objections", "objection_type": "security", "tier": "all"}
    },
    {
        "id": "obj_006",
        "text": "Objection: 'The implementation seems complex' or 'We don't have technical resources'. Response: Reassure with onboarding support: 'Pro Plan includes a dedicated onboarding specialist who handles the setup for you.' Share the LogiCorp story: went live in 3 weeks. Offer a technical demo showing how simple the integration is. Mention our Zapier and native integrations that require zero coding.",
        "metadata": {"collection": "objections", "objection_type": "implementation", "tier": "all"}
    },
    {
        "id": "obj_007",
        "text": "Objection: 'We're a small team, this seems like overkill'. Response: Validate their concern, then right-size: 'You're right — that's exactly why we have the Starter Plan at $29/month. It's designed for small teams and you only upgrade when you need to.' Emphasize the free trial: 'Start with Starter, no commitment, and you'll see within 2 weeks whether it fits.' Many small teams find they grow into Pro within 6 months.",
        "metadata": {"collection": "objections", "objection_type": "too_big", "tier": "smb"}
    },
]


def main():
    print("Seeding sales knowledge bases...")

    collections = {
        "products": PRODUCTS,
        "success_stories": SUCCESS_STORIES,
        "objections": OBJECTIONS
    }

    for collection_name, docs in collections.items():
        collection = get_collection(collection_name)
        existing_ids = set(collection.get()["ids"])
        new_docs = [d for d in docs if d["id"] not in existing_ids]

        if not new_docs:
            print(f"'{collection_name}' already seeded ({len(docs)} docs)")
            continue

        print(f"Seeding '{collection_name}' — adding {len(new_docs)} docs...")
        add_documents(collection_name, new_docs)
        print(f"'{collection_name}' done — {collection.count()} total docs")

    print("\nAll knowledge bases seeded successfully!")


if __name__ == "__main__":
    main()