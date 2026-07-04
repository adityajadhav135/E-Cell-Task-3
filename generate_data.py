import json
import random
import os
from pathlib import Path
from datetime import datetime, timedelta
from google import genai
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

INDUSTRIES  = ["SaaS", "E-commerce", "Healthcare", "Finance", "Education", "Logistics", "Retail", "Manufacturing"]
PLANS       = ["Free", "Starter", "Pro", "Enterprise"]
TICKET_CATS = ["Billing", "Technical", "Account", "Feature Request", "Onboarding", "Security", "Performance"]
PRIORITIES  = ["Low", "Medium", "High", "Critical"]
STATUSES    = ["Open", "In Progress", "Escalated", "Resolved", "Closed"]
AGENTS      = ["agent_001", "agent_002", "agent_003", "agent_004", "agent_005"]


def random_date(start_days_ago=180, end_days_ago=0):
    days = random.randint(end_days_ago, start_days_ago)
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


def generate_customers_batch(batch_num, batch_size=50):
    prompt = f"""Generate {batch_size} realistic synthetic CRM customer profiles as a JSON array.
Each customer must have exactly these fields:
- customer_id: string like "CUST_{batch_num:02d}_001" through "CUST_{batch_num:02d}_{batch_size:03d}"
- name: realistic full name
- email: realistic email
- company: realistic company name
- industry: one of {INDUSTRIES}
- plan: one of {PLANS}
- acquisition_date: ISO date between 2024-01-01 and 2025-01-01
- engagement_score: float between 0.1 and 1.0
- nps_score: integer between -100 and 100
- total_tickets: integer between 0 and 20
- is_churned: boolean (20% chance true)
- country: realistic country name
- onboarding_completed: boolean (70% chance true)

Return ONLY a valid JSON array, no explanation, no markdown, no backticks."""

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = response.text.strip().replace("```json", "").replace("```", "").strip()
    customers = json.loads(text)
    print(f"  Batch {batch_num}: {len(customers)} customers generated")
    return customers


def generate_all_customers():
    print("\n" + "="*50)
    print("GENERATING 500 CUSTOMERS...")
    print("="*50)

    all_customers = []

    for batch in range(1, 11):
        try:
            all_customers.extend(generate_customers_batch(batch, 50))
        except Exception as e:
            print(f"  Batch {batch} failed: {e}, generating locally...")
            for i in range(50):
                all_customers.append({
                    "customer_id": f"CUST_{batch:02d}_{i+1:03d}",
                    "name": f"Customer {len(all_customers)+1}",
                    "email": f"customer{len(all_customers)+1}@example.com",
                    "company": f"Company {len(all_customers)+1}",
                    "industry": random.choice(INDUSTRIES),
                    "plan": random.choice(PLANS),
                    "acquisition_date": random_date(500, 30),
                    "engagement_score": round(random.uniform(0.1, 1.0), 2),
                    "nps_score": random.randint(-100, 100),
                    "total_tickets": random.randint(0, 20),
                    "is_churned": random.random() < 0.2,
                    "country": random.choice(["USA", "India", "UK", "Germany", "Canada"]),
                    "onboarding_completed": random.random() < 0.7,
                })

    with open(DATA_DIR / "customers.json", "w") as f:
        json.dump(all_customers, f, indent=2)
    print(f"\n✓ Saved {len(all_customers)} customers → data/customers.json")
    return all_customers


def generate_tickets_batch(customers, batch_num, batch_size=50):
    sample_ids = [c["customer_id"] for c in random.sample(customers, min(batch_size, len(customers)))]

    prompt = f"""Generate {batch_size} realistic CRM support tickets as a JSON array.
Use these customer IDs (assign randomly): {sample_ids[:10]}
Each ticket must have exactly these fields:
- ticket_id: string like "TICK_{batch_num:02d}_001" through "TICK_{batch_num:02d}_{batch_size:03d}"
- customer_id: one of the customer IDs listed above
- title: realistic support ticket title
- description: 2-3 sentence realistic problem description
- category: one of {TICKET_CATS}
- priority: one of {PRIORITIES}
- status: one of {STATUSES}
- assigned_agent: one of {AGENTS}
- created_at: ISO datetime between 2024-07-01 and 2025-06-01
- resolved_at: ISO datetime or null (null if status is Open or In Progress)
- resolution_time_hours: integer or null (null if not resolved)
- csat_score: integer 1-5 or null (null if not resolved)

Return ONLY a valid JSON array, no explanation, no markdown, no backticks."""

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = response.text.strip().replace("```json", "").replace("```", "").strip()
    tickets = json.loads(text)
    print(f"  Batch {batch_num}: {len(tickets)} tickets generated")
    return tickets


def generate_all_tickets(customers):
    print("\n" + "="*50)
    print("GENERATING 1000 TICKETS...")
    print("="*50)

    all_tickets = []

    for batch in range(1, 21):
        try:
            all_tickets.extend(generate_tickets_batch(customers, batch, 50))
        except Exception as e:
            print(f"  Batch {batch} failed: {e}, generating locally...")
            for i in range(50):
                customer = random.choice(customers)
                status = random.choice(STATUSES)
                resolved = status in ["Resolved", "Closed"]
                all_tickets.append({
                    "ticket_id": f"TICK_{batch:02d}_{i+1:03d}",
                    "customer_id": customer["customer_id"],
                    "title": f"Issue with {random.choice(TICKET_CATS)}",
                    "description": "Customer reported an issue that needs resolution.",
                    "category": random.choice(TICKET_CATS),
                    "priority": random.choice(PRIORITIES),
                    "status": status,
                    "assigned_agent": random.choice(AGENTS),
                    "created_at": random_date(180, 1),
                    "resolved_at": random_date(30, 0) if resolved else None,
                    "resolution_time_hours": random.randint(1, 72) if resolved else None,
                    "csat_score": random.randint(1, 5) if resolved else None,
                })

    with open(DATA_DIR / "tickets.json", "w") as f:
        json.dump(all_tickets, f, indent=2)
    print(f"\n✓ Saved {len(all_tickets)} tickets → data/tickets.json")
    return all_tickets


def generate_interaction_logs(customers, tickets):
    print("\n" + "="*50)
    print("GENERATING INTERACTION LOGS...")
    print("="*50)

    logs = []
    interaction_types = ["email", "call", "chat", "ticket_update", "login", "feature_use"]

    for customer in customers:
        for j in range(random.randint(5, 15)):
            logs.append({
                "log_id": f"LOG_{customer['customer_id']}_{j+1:03d}",
                "customer_id": customer["customer_id"],
                "type": random.choice(interaction_types),
                "timestamp": random_date(180, 0),
                "duration_minutes": random.randint(1, 60),
                "agent_id": random.choice(AGENTS + [None]),
                "notes": f"Customer interaction via {random.choice(interaction_types)}",
                "sentiment": random.choice(["positive", "neutral", "negative"]),
            })

    with open(DATA_DIR / "interaction_logs.json", "w") as f:
        json.dump(logs, f, indent=2)
    print(f"✓ Saved {len(logs)} interaction logs → data/interaction_logs.json")
    return logs


if __name__ == "__main__":
    print("\n" + "="*50)
    print("E-CELL TASK 3 — SYNTHETIC DATA GENERATION")
    print("="*50)

    customers = generate_all_customers()
    tickets   = generate_all_tickets(customers)
    logs      = generate_interaction_logs(customers, tickets)

    print("\n" + "="*50)
    print("DATA GENERATION COMPLETE")
    print("="*50)
    print(f"  Customers        : {len(customers)}")
    print(f"  Tickets          : {len(tickets)}")
    print(f"  Interaction logs : {len(logs)}")
    print("="*50)