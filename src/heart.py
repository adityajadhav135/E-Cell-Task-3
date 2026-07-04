import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path("data")


def load_json(path: Path):
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def compute_happiness(customers: list, tickets: list) -> dict:
    csat_scores = [t["csat_score"] for t in tickets if t.get("csat_score")]
    nps_scores  = [c.get("nps_score", 0) for c in customers]

    avg_csat = round(sum(csat_scores) / max(len(csat_scores), 1), 4)
    avg_nps  = round(sum(nps_scores)  / max(len(nps_scores),  1), 2)

    normalized_csat = round(avg_csat / 5.0, 4)
    normalized_nps  = round((avg_nps + 100) / 200, 4)
    score           = round((normalized_csat * 0.6 + normalized_nps * 0.4), 4)

    by_category = defaultdict(list)
    for t in tickets:
        if t.get("csat_score"):
            by_category[t.get("category", "Unknown")].append(t["csat_score"])

    category_scores = {
        cat: round(sum(scores) / len(scores), 2)
        for cat, scores in by_category.items()
    }

    return {
        "score":            score,
        "avg_csat":         avg_csat,
        "avg_nps":          avg_nps,
        "total_responses":  len(csat_scores),
        "category_scores":  category_scores,
    }


def compute_engagement(customers: list, tickets: list, logs: list) -> dict:
    now        = datetime.now()
    week_ago   = now - timedelta(days=7)
    week_str   = week_ago.strftime("%Y-%m-%dT%H:%M:%S")

    active_ids = set()
    for l in logs:
        if l.get("timestamp", "") >= week_str:
            active_ids.add(l["customer_id"])
    for t in tickets:
        if t.get("created_at", "") >= week_str:
            active_ids.add(t["customer_id"])

    active_weekly    = len(active_ids)
    ticket_open_rate = round(
        len([t for t in tickets if t["status"] == "Open"]) / max(len(tickets), 1), 4
    )

    total_duration  = sum(l.get("duration_minutes", 0) for l in logs)
    avg_duration    = round(total_duration / max(len(logs), 1), 2)

    thread_depth = defaultdict(int)
    for t in tickets:
        thread_depth[t["customer_id"]] += 1
    avg_thread_depth = round(
        sum(thread_depth.values()) / max(len(thread_depth), 1), 2
    )

    score = round(
        (active_weekly / max(len(customers), 1)) * 0.4
        + (1 - ticket_open_rate) * 0.3
        + min(avg_duration / 60, 1.0) * 0.3,
        4
    )

    return {
        "score":             score,
        "active_weekly":     active_weekly,
        "ticket_open_rate":  ticket_open_rate,
        "avg_session_mins":  avg_duration,
        "avg_thread_depth":  avg_thread_depth,
    }


def compute_adoption(customers: list, tickets: list, logs: list) -> dict:
    onboarded = sum(1 for c in customers if c.get("onboarding_completed"))
    onboarding_rate = round(onboarded / max(len(customers), 1), 4)

    customers_with_tickets = len({t["customer_id"] for t in tickets})
    feature_adoption_rate  = round(customers_with_tickets / max(len(customers), 1), 4)

    customers_with_logs = len({l["customer_id"] for l in logs})
    ai_interaction_rate = round(customers_with_logs / max(len(customers), 1), 4)

    score = round(
        onboarding_rate   * 0.4
        + feature_adoption_rate * 0.3
        + ai_interaction_rate   * 0.3,
        4
    )

    return {
        "score":                score,
        "onboarding_rate":      onboarding_rate,
        "feature_adoption_rate": feature_adoption_rate,
        "ai_interaction_rate":  ai_interaction_rate,
        "onboarded_customers":  onboarded,
    }


def compute_retention(customers: list, tickets: list, logs: list) -> dict:
    total   = len(customers)
    churned = sum(1 for c in customers if c.get("is_churned"))
    monthly_retention = round(1 - (churned / max(total, 1)), 4)

    now = datetime.now()
    monthly_curves = []

    for month_offset in range(6):
        month_start = (now - timedelta(days=30 * (5 - month_offset))).strftime("%Y-%m-%dT%H:%M:%S")
        month_end   = (now - timedelta(days=30 * (4 - month_offset))).strftime("%Y-%m-%dT%H:%M:%S")

        active = set()
        for l in logs:
            if month_start <= l.get("timestamp", "") <= month_end:
                active.add(l["customer_id"])
        for t in tickets:
            if month_start <= t.get("created_at", "") <= month_end:
                active.add(t["customer_id"])

        monthly_curves.append({
            "month":          month_offset + 1,
            "active":         len(active),
            "retention_rate": round(len(active) / max(total, 1), 4),
        })

    lifespan_days = []
    for c in customers:
        acq = c.get("acquisition_date", "")
        if acq:
            try:
                days = (now - datetime.fromisoformat(acq[:10])).days
                lifespan_days.append(days)
            except Exception:
                pass

    avg_lifespan = round(sum(lifespan_days) / max(len(lifespan_days), 1), 1)

    score = round(monthly_retention * 0.6 + min(avg_lifespan / 365, 1.0) * 0.4, 4)

    return {
        "score":              score,
        "monthly_retention":  monthly_retention,
        "churned_customers":  churned,
        "churn_rate":         round(churned / max(total, 1), 4),
        "avg_lifespan_days":  avg_lifespan,
        "monthly_curves":     monthly_curves,
    }


def compute_task_success(tickets: list) -> dict:
    total    = len(tickets)
    resolved = [t for t in tickets if t["status"] in ["Resolved", "Closed"]]
    escalated = [t for t in tickets if t["status"] == "Escalated"]

    resolution_rate   = round(len(resolved) / max(total, 1), 4)
    escalation_rate   = round(len(escalated) / max(total, 1), 4)

    times = [t["resolution_time_hours"] for t in resolved if t.get("resolution_time_hours")]
    avg_resolution = round(sum(times) / max(len(times), 1), 2)

    first_contact = [t for t in resolved if t.get("resolution_time_hours", 999) <= 4]
    first_contact_rate = round(len(first_contact) / max(len(resolved), 1), 4)

    score = round(
        resolution_rate     * 0.4
        + (1 - escalation_rate) * 0.3
        + first_contact_rate    * 0.3,
        4
    )

    return {
        "score":               score,
        "resolution_rate":     resolution_rate,
        "escalation_rate":     escalation_rate,
        "first_contact_rate":  first_contact_rate,
        "avg_resolution_hours": avg_resolution,
        "total_tickets":       total,
        "resolved_tickets":    len(resolved),
    }


def compute_heart_scores() -> dict:
    customers = load_json(DATA_DIR / "customers.json")
    tickets   = load_json(DATA_DIR / "tickets.json")
    logs      = load_json(DATA_DIR / "interaction_logs.json")

    happiness   = compute_happiness(customers, tickets)
    engagement  = compute_engagement(customers, tickets, logs)
    adoption    = compute_adoption(customers, tickets, logs)
    retention   = compute_retention(customers, tickets, logs)
    task_success = compute_task_success(tickets)

    overall = round(
        happiness["score"]    * 0.2
        + engagement["score"] * 0.2
        + adoption["score"]   * 0.2
        + retention["score"]  * 0.2
        + task_success["score"] * 0.2,
        4
    )

    result = {
        "computed_at":   datetime.now().isoformat(),
        "overall_score": overall,
        "happiness":     happiness,
        "engagement":    engagement,
        "adoption":      adoption,
        "retention":     retention,
        "task_success":  task_success,
    }

    output_path = DATA_DIR / "heart_scores.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    result = compute_heart_scores()

    print(f"Overall HEART Score : {result['overall_score']}")
    print(f"Happiness           : {result['happiness']['score']}")
    print(f"Engagement          : {result['engagement']['score']}")
    print(f"Adoption            : {result['adoption']['score']}")
    print(f"Retention           : {result['retention']['score']}")
    print(f"Task Success        : {result['task_success']['score']}")
    print(f"Saved to data/heart_scores.json")