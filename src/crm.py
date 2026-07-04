import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

DATA_DIR = Path("../Data")
CUSTOMERS_FILE = DATA_DIR / "customers.json"
TICKETS_FILE = DATA_DIR / "tickets.json"
LOGS_FILE = DATA_DIR / "interaction_logs.json"

VALID_STATUSES = ["Open", "In Progress", "Escalated", "Resolved", "Closed"]
VALID_PRIORITIES = ["Low", "Medium", "High", "Critical"]


def load_json(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, "r") as f:
        return json.load(f)


def save_json(path: Path, data: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_all_customers() -> list:
    return load_json(CUSTOMERS_FILE)


def get_customer_by_id(customer_id: str) -> Optional[dict]:
    customers = get_all_customers()
    for c in customers:
        if c["customer_id"] == customer_id:
            return c
    return None


def create_customer(data: dict) -> dict:
    customers = get_all_customers()

    for c in customers:
        if c.get("email") == data.get("email"):
            raise ValueError(f"Customer with email {data['email']} already exists.")

    customer = {
        "customer_id": f"CUST_{uuid.uuid4().hex[:8].upper()}",
        "name": data.get("name", "Unknown"),
        "email": data.get("email", ""),
        "company": data.get("company", ""),
        "industry": data.get("industry", "Other"),
        "plan": data.get("plan", "Free"),
        "acquisition_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "engagement_score": data.get("engagement_score", 0.5),
        "nps_score": data.get("nps_score", 0),
        "total_tickets": 0,
        "is_churned": False,
        "country": data.get("country", "Unknown"),
        "onboarding_completed": data.get("onboarding_completed", False),
        "segment": assign_segment(data),
    }

    customers.append(customer)
    save_json(CUSTOMERS_FILE, customers)
    return customer


def update_customer(customer_id: str, updates: dict) -> dict:
    customers = get_all_customers()

    for i, c in enumerate(customers):
        if c["customer_id"] == customer_id:
            customers[i].update(updates)
            save_json(CUSTOMERS_FILE, customers)
            return customers[i]

    raise ValueError(f"Customer {customer_id} not found.")


def delete_customer(customer_id: str) -> bool:
    customers = get_all_customers()
    new_list = [c for c in customers if c["customer_id"] != customer_id]

    if len(new_list) == len(customers):
        raise ValueError(f"Customer {customer_id} not found.")

    save_json(CUSTOMERS_FILE, new_list)
    return True


def assign_segment(data: dict) -> str:
    score = data.get("engagement_score", 0.5)
    plan = data.get("plan", "Free")
    tickets = data.get("total_tickets", 0)

    if plan == "Enterprise" and score >= 0.7:
        return "High Value"
    elif plan in ["Pro", "Enterprise"] and score >= 0.4:
        return "Growth"
    elif tickets >= 10:
        return "At Risk"
    elif score < 0.3:
        return "Dormant"
    else:
        return "Standard"


def get_customer_timeline(customer_id: str) -> list:
    tickets = get_all_tickets()
    logs = load_json(LOGS_FILE)

    events = []

    for t in tickets:
        if t["customer_id"] == customer_id:
            events.append({
                "timestamp": t["created_at"],
                "type": "ticket",
                "id": t["ticket_id"],
                "summary": t["title"],
                "status": t["status"],
            })

    for l in logs:
        if l["customer_id"] == customer_id:
            events.append({
                "timestamp": l["timestamp"],
                "type": l["type"],
                "id": l["log_id"],
                "summary": l["notes"],
                "sentiment": l.get("sentiment", "neutral"),
            })

    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events


def get_all_tickets() -> list:
    return load_json(TICKETS_FILE)


def get_ticket_by_id(ticket_id: str) -> Optional[dict]:
    tickets = get_all_tickets()
    for t in tickets:
        if t["ticket_id"] == ticket_id:
            return t
    return None


def create_ticket(data: dict) -> dict:
    tickets = get_all_tickets()
    customers = get_all_customers()

    customer = get_customer_by_id(data.get("customer_id", ""))
    if not customer:
        raise ValueError(f"Customer {data.get('customer_id')} not found.")

    ticket = {
        "ticket_id": f"TICK_{uuid.uuid4().hex[:8].upper()}",
        "customer_id": data["customer_id"],
        "title": data.get("title", "Untitled"),
        "description": data.get("description", ""),
        "category": data.get("category", "General"),
        "priority": data.get("priority", "Medium"),
        "status": "Open",
        "assigned_agent": data.get("assigned_agent", "agent_001"),
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "resolved_at": None,
        "resolution_time_hours": None,
        "csat_score": None,
    }

    tickets.append(ticket)
    save_json(TICKETS_FILE, tickets)

    for i, c in enumerate(customers):
        if c["customer_id"] == data["customer_id"]:
            customers[i]["total_tickets"] = customers[i].get("total_tickets", 0) + 1
            save_json(CUSTOMERS_FILE, customers)
            break

    return ticket


def update_ticket_status(ticket_id: str, new_status: str, csat_score: int = None) -> dict:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status. Must be one of {VALID_STATUSES}")

    tickets = get_all_tickets()

    for i, t in enumerate(tickets):
        if t["ticket_id"] == ticket_id:
            tickets[i]["status"] = new_status

            if new_status in ["Resolved", "Closed"]:
                tickets[i]["resolved_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

                created = datetime.fromisoformat(tickets[i]["created_at"])
                resolved = datetime.now()
                tickets[i]["resolution_time_hours"] = int((resolved - created).total_seconds() / 3600)

                if csat_score:
                    tickets[i]["csat_score"] = csat_score

            save_json(TICKETS_FILE, tickets)
            return tickets[i]

    raise ValueError(f"Ticket {ticket_id} not found.")


def get_tickets_by_customer(customer_id: str) -> list:
    tickets = get_all_tickets()
    return [t for t in tickets if t["customer_id"] == customer_id]


def get_tickets_by_status(status: str) -> list:
    tickets = get_all_tickets()
    return [t for t in tickets if t["status"] == status]


def get_segmented_customers() -> dict:
    customers = get_all_customers()
    segments = {}

    for c in customers:
        seg = c.get("segment") or assign_segment(c)
        if seg not in segments:
            segments[seg] = []
        segments[seg].append(c["customer_id"])

    return segments


def get_crm_stats() -> dict:
    customers = get_all_customers()
    tickets = get_all_tickets()

    total = len(customers)
    churned = sum(1 for c in customers if c.get("is_churned"))
    resolved = [t for t in tickets if t["status"] in ["Resolved", "Closed"]]
    avg_resolution = (
        sum(t["resolution_time_hours"] for t in resolved if t["resolution_time_hours"])
        / max(len(resolved), 1)
    )

    return {
        "total_customers": total,
        "churned_customers": churned,
        "churn_rate": round(churned / max(total, 1), 4),
        "total_tickets": len(tickets),
        "resolved_tickets": len(resolved),
        "resolution_rate": round(len(resolved) / max(len(tickets), 1), 4),
        "avg_resolution_time_hours": round(avg_resolution, 2),
        "segments": get_segmented_customers(),
    }


if __name__ == "__main__":
    stats = get_crm_stats()
    print(json.dumps(stats, indent=2))