import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()

DATA_DIR   = Path("data")
MEMORY_DIR = Path("models/memory")
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL  = "gemini-2.0-flash"

AGENTS      = ["agent_001", "agent_002", "agent_003", "agent_004", "agent_005"]
CATEGORIES  = ["Billing", "Technical", "Account", "Feature Request", "Onboarding", "Security", "Performance"]
PRIORITIES  = ["Low", "Medium", "High", "Critical"]


def load_json(path: Path) -> list:
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def call_gemini(prompt: str) -> str:
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text.strip()


def summarize_ticket(ticket: dict) -> dict:
    prompt = f"""You are a CRM support assistant. Summarize this support ticket concisely.

Ticket ID   : {ticket['ticket_id']}
Customer ID : {ticket['customer_id']}
Title       : {ticket['title']}
Description : {ticket['description']}
Category    : {ticket['category']}
Priority    : {ticket['priority']}
Status      : {ticket['status']}

Respond in this exact JSON format with no markdown:
{{
  "key_issues": "one sentence describing the core problem",
  "urgency": "Low / Medium / High / Critical",
  "suggested_action": "one sentence on what the agent should do",
  "suggested_response": "a short professional reply to send to the customer"
}}"""

    raw = call_gemini(prompt)
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except Exception:
        return {
            "key_issues": ticket["description"][:100],
            "urgency": ticket["priority"],
            "suggested_action": "Review and respond to customer.",
            "suggested_response": "Thank you for reaching out. We are looking into your issue.",
        }


def route_ticket(ticket: dict) -> dict:
    priority_agent_map = {
        "Critical": "agent_001",
        "High":     "agent_002",
        "Medium":   "agent_003",
        "Low":      "agent_004",
    }

    category_agent_map = {
        "Billing":         "agent_005",
        "Security":        "agent_001",
        "Technical":       "agent_002",
        "Account":         "agent_003",
        "Feature Request": "agent_004",
        "Onboarding":      "agent_003",
        "Performance":     "agent_002",
    }

    priority    = ticket.get("priority", "Medium")
    category    = ticket.get("category", "Technical")
    should_escalate = priority == "Critical"

    if should_escalate:
        assigned = "agent_001"
        new_status = "Escalated"
    else:
        assigned   = category_agent_map.get(category, priority_agent_map.get(priority, "agent_003"))
        new_status = "In Progress"

    return {
        "ticket_id":      ticket["ticket_id"],
        "assigned_agent": assigned,
        "new_status":     new_status,
        "escalated":      should_escalate,
        "routing_reason": f"Category={category}, Priority={priority}",
    }


def run_agent_workflow(ticket: dict) -> dict:
    state = {
        "ticket":    ticket,
        "stage":     "start",
        "history":   [],
        "summary":   None,
        "routing":   None,
        "response":  None,
        "completed": False,
    }

    state["history"].append({"stage": "start", "timestamp": datetime.now().isoformat()})
    state["stage"] = "summarize"

    summary = summarize_ticket(ticket)
    state["summary"] = summary
    state["history"].append({"stage": "summarize", "output": summary, "timestamp": datetime.now().isoformat()})

    state["stage"] = "route"
    routing = route_ticket(ticket)
    state["routing"] = routing
    state["history"].append({"stage": "route", "output": routing, "timestamp": datetime.now().isoformat()})

    state["stage"] = "respond"
    state["response"] = summary.get("suggested_response", "We are looking into your issue.")
    state["history"].append({"stage": "respond", "output": state["response"], "timestamp": datetime.now().isoformat()})

    if routing.get("escalated"):
        state["stage"] = "escalate"
        state["history"].append({
            "stage":     "escalate",
            "output":    f"Escalated to {routing['assigned_agent']}",
            "timestamp": datetime.now().isoformat(),
        })

    state["stage"]     = "complete"
    state["completed"] = True
    state["history"].append({"stage": "complete", "timestamp": datetime.now().isoformat()})

    return state


def query_agent(customer_id: str, query: str, chat_history: list = None) -> dict:
    tickets = load_json(DATA_DIR / "tickets.json")
    logs    = load_json(DATA_DIR / "interaction_logs.json")

    customer_tickets = [t for t in tickets if t["customer_id"] == customer_id]
    customer_logs    = [l for l in logs if l["customer_id"] == customer_id]

    recent_tickets = customer_tickets[-5:]
    recent_logs    = customer_logs[-5:]

    history_text = ""
    if chat_history:
        for msg in chat_history[-6:]:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            history_text += f"{role.upper()}: {content}\n"

    prompt = f"""You are an AI CRM assistant. Answer the agent's query about this customer using only the data provided below.
If the answer is not in the data, say "I don't have enough information about this."

Customer ID : {customer_id}

Recent Tickets:
{json.dumps(recent_tickets, indent=2)}

Recent Interactions:
{json.dumps(recent_logs, indent=2)}

Chat History:
{history_text if history_text else "No prior history."}

Agent Query: {query}

Respond concisely and factually. Cite ticket IDs or log IDs where relevant."""

    answer = call_gemini(prompt)

    return {
        "customer_id": customer_id,
        "query":       query,
        "answer":      answer,
        "source":      "CRM data",
        "confidence":  0.85,
        "agent_id":    "agent_001",
        "timestamp":   datetime.now().isoformat(),
    }


def batch_process_tickets(limit: int = 10) -> list:
    tickets = load_json(DATA_DIR / "tickets.json")
    open_tickets = [t for t in tickets if t["status"] == "Open"][:limit]

    results = []
    for ticket in open_tickets:
        print(f"  Processing {ticket['ticket_id']}...")
        result = run_agent_workflow(ticket)
        results.append({
            "ticket_id": ticket["ticket_id"],
            "summary":   result["summary"],
            "routing":   result["routing"],
            "completed": result["completed"],
        })

    save_json(DATA_DIR / "agent_results.json", results)
    print(f"\n✓ Processed {len(results)} tickets → data/agent_results.json")
    return results


if __name__ == "__main__":
    print("\n" + "="*50)
    print("AGENTS.PY — TESTING AGENT WORKFLOW")
    print("="*50)

    tickets = load_json(DATA_DIR / "tickets.json")

    if tickets:
        ticket = tickets[0]
        print(f"\nRunning workflow for ticket: {ticket['ticket_id']}")
        result = run_agent_workflow(ticket)
        print(json.dumps(result, indent=2))
    else:
        print("No tickets found. Run generate_data.py first.")