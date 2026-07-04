import json
import math
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path("data")


def load_json(path: Path):
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def assign_cohort(customer: dict) -> str:
    acq = customer.get("acquisition_date", "")
    plan = customer.get("plan", "Free")
    industry = customer.get("industry", "Other")

    if acq:
        try:
            date = datetime.fromisoformat(acq[:10])
            month_label = date.strftime("%Y-%m")
            return f"{month_label}_{plan}"
        except Exception:
            pass

    return f"Unknown_{plan}"


def build_cohorts(customers: list) -> dict:
    cohorts = defaultdict(list)

    for c in customers:
        cohort_id = assign_cohort(c)
        cohorts[cohort_id].append(c)

    return dict(cohorts)


def compute_retention_curve(cohort_customers: list, tickets: list, logs: list) -> list:
    if not cohort_customers:
        return []

    customer_ids = {c["customer_id"] for c in cohort_customers}
    total        = len(customer_ids)
    curve        = []

    for month_offset in range(6):
        cutoff_date = datetime.now() - timedelta(days=30 * (5 - month_offset))
        cutoff_str  = cutoff_date.strftime("%Y-%m-%dT%H:%M:%S")

        active = set()

        for t in tickets:
            if t["customer_id"] in customer_ids and t["created_at"] <= cutoff_str:
                active.add(t["customer_id"])

        for l in logs:
            if l["customer_id"] in customer_ids and l["timestamp"] <= cutoff_str:
                active.add(l["customer_id"])

        retention_rate = round(len(active) / max(total, 1), 4)
        curve.append({
            "month":          month_offset + 1,
            "date":           cutoff_date.strftime("%Y-%m"),
            "active":         len(active),
            "total":          total,
            "retention_rate": retention_rate,
        })

    return curve


def compute_churn_score(customer: dict, tickets: list, logs: list) -> float:
    customer_id = customer["customer_id"]
    score       = 0.0

    if customer.get("is_churned"):
        return 1.0

    engagement = customer.get("engagement_score", 0.5)
    score += (1 - engagement) * 0.3

    customer_tickets = [t for t in tickets if t["customer_id"] == customer_id]
    if len(customer_tickets) == 0:
        score += 0.2
    elif len(customer_tickets) >= 10:
        score += 0.1

    critical_tickets = [t for t in customer_tickets if t.get("priority") == "Critical"]
    score += min(len(critical_tickets) * 0.05, 0.2)

    customer_logs = [l for l in logs if l["customer_id"] == customer_id]
    negative_logs = [l for l in customer_logs if l.get("sentiment") == "negative"]
    if customer_logs:
        score += (len(negative_logs) / len(customer_logs)) * 0.2

    nps = customer.get("nps_score", 0)
    if nps < -20:
        score += 0.15
    elif nps < 0:
        score += 0.05

    if not customer.get("onboarding_completed"):
        score += 0.1

    acq = customer.get("acquisition_date", "")
    if acq:
        try:
            acq_date    = datetime.fromisoformat(acq[:10])
            days_active = (datetime.now() - acq_date).days
            if days_active < 30:
                score += 0.1
        except Exception:
            pass

    return round(min(score, 1.0), 4)


def compute_cohort_metrics(cohort_id: str, cohort_customers: list, tickets: list, logs: list) -> dict:
    customer_ids = [c["customer_id"] for c in cohort_customers]
    total        = len(cohort_customers)
    churned      = sum(1 for c in cohort_customers if c.get("is_churned"))

    cohort_tickets = [t for t in tickets if t["customer_id"] in customer_ids]
    resolved       = [t for t in cohort_tickets if t["status"] in ["Resolved", "Closed"]]

    avg_resolution = 0.0
    if resolved:
        times          = [t["resolution_time_hours"] for t in resolved if t.get("resolution_time_hours")]
        avg_resolution = round(sum(times) / max(len(times), 1), 2)

    avg_engagement = round(
        sum(c.get("engagement_score", 0) for c in cohort_customers) / max(total, 1), 4
    )

    avg_nps = round(
        sum(c.get("nps_score", 0) for c in cohort_customers) / max(total, 1), 2
    )

    churn_scores = [compute_churn_score(c, tickets, logs) for c in cohort_customers]
    avg_churn_score = round(sum(churn_scores) / max(len(churn_scores), 1), 4)

    high_risk = [
        c["customer_id"]
        for c, score in zip(cohort_customers, churn_scores)
        if score >= 0.6
    ]

    retention_curve = compute_retention_curve(cohort_customers, tickets, logs)

    return {
        "cohort_id":              cohort_id,
        "total_customers":        total,
        "churned_customers":      churned,
        "churn_rate":             round(churned / max(total, 1), 4),
        "avg_churn_score":        avg_churn_score,
        "high_risk_customers":    high_risk,
        "avg_engagement_score":   avg_engagement,
        "avg_nps_score":          avg_nps,
        "total_tickets":          len(cohort_tickets),
        "resolved_tickets":       len(resolved),
        "resolution_rate":        round(len(resolved) / max(len(cohort_tickets), 1), 4),
        "avg_resolution_hours":   avg_resolution,
        "retention_curve":        retention_curve,
    }


def run_full_cohort_analysis() -> dict:
    customers = load_json(DATA_DIR / "customers.json")
    tickets   = load_json(DATA_DIR / "tickets.json")
    logs      = load_json(DATA_DIR / "interaction_logs.json")

    cohorts = build_cohorts(customers)
    results = {}

    for cohort_id, cohort_customers in cohorts.items():
        metrics = compute_cohort_metrics(cohort_id, cohort_customers, tickets, logs)
        results[cohort_id] = metrics

    summary = {
        "total_cohorts":    len(results),
        "total_customers":  len(customers),
        "analysis_date":    datetime.now().isoformat(),
        "cohorts":          results,
    }

    save_json(DATA_DIR / "cohort_analysis.json", summary)
    return summary


def get_cohort_by_customer(customer_id: str) -> Optional[str]:
    customers = load_json(DATA_DIR / "customers.json")
    for c in customers:
        if c["customer_id"] == customer_id:
            return assign_cohort(c)
    return None


def get_high_risk_customers(threshold: float = 0.6) -> list:
    customers = load_json(DATA_DIR / "customers.json")
    tickets   = load_json(DATA_DIR / "tickets.json")
    logs      = load_json(DATA_DIR / "interaction_logs.json")

    results = []
    for c in customers:
        score = compute_churn_score(c, tickets, logs)
        if score >= threshold:
            results.append({
                "customer_id":  c["customer_id"],
                "name":         c.get("name"),
                "plan":         c.get("plan"),
                "churn_score":  score,
                "is_churned":   c.get("is_churned"),
            })

    results.sort(key=lambda x: x["churn_score"], reverse=True)
    return results


if __name__ == "__main__":
    from typing import Optional

    print("\n" + "="*50)
    print("RUNNING COHORT ANALYSIS...")
    print("="*50)

    analysis = run_full_cohort_analysis()

    print(f"\nTotal cohorts    : {analysis['total_cohorts']}")
    print(f"Total customers  : {analysis['total_customers']}")
    print(f"Analysis saved   → data/cohort_analysis.json")

    print("\nTop 3 cohorts by size:")
    sorted_cohorts = sorted(
        analysis["cohorts"].items(),
        key=lambda x: x[1]["total_customers"],
        reverse=True
    )

    for cohort_id, metrics in sorted_cohorts[:3]:
        print(f"\n  Cohort : {cohort_id}")
        print(f"  Size   : {metrics['total_customers']}")
        print(f"  Churn  : {metrics['churn_rate']:.1%}")
        print(f"  Avg Churn Score : {metrics['avg_churn_score']}")
        print(f"  High Risk Count : {len(metrics['high_risk_customers'])}")

    print("\nTop 5 high risk customers:")
    high_risk = get_high_risk_customers()[:5]
    for c in high_risk:
        print(f"  {c['customer_id']} | score={c['churn_score']} | plan={c['plan']}")