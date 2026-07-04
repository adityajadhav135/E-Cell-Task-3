import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.append(str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import secrets

from crm import (
    get_all_customers, get_customer_by_id, create_customer,
    update_customer, delete_customer, get_customer_timeline,
    get_all_tickets, get_ticket_by_id, create_ticket,
    update_ticket_status, get_tickets_by_customer,
    get_tickets_by_status, get_crm_stats
)
from agents import summarize_ticket, route_ticket, run_agent_workflow, query_agent
from memory import load_memory, add_to_long_term, chat_with_memory, summarize_memory, get_memory_stats
from cohort import run_full_cohort_analysis, get_high_risk_customers, compute_churn_score
from heart import compute_heart_scores


app = FastAPI(
    title="E-Cell CRM API",
    description="AI-integrated CRM platform with LangChain agents, cohort analysis, and HEART framework dashboard.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()

ROLES = {
    "admin":      {"password": "admin123",      "role": "Admin"},
    "agent":      {"password": "agent123",      "role": "Agent"},
    "supervisor": {"password": "supervisor123", "role": "Supervisor"},
    "analytics":  {"password": "analytics123",  "role": "Analytics"},
}


def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password

    user = ROLES.get(username)
    if not user or not secrets.compare_digest(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    return {"username": username, "role": user["role"]}


def require_role(allowed_roles: list):
    def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Role {user['role']} not authorized.")
        return user
    return checker


class CustomerCreate(BaseModel):
    name: str
    email: str
    company: str
    industry: Optional[str] = "Other"
    plan: Optional[str] = "Free"
    country: Optional[str] = "Unknown"
    engagement_score: Optional[float] = 0.5
    nps_score: Optional[int] = 0
    onboarding_completed: Optional[bool] = False


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    plan: Optional[str] = None
    engagement_score: Optional[float] = None
    nps_score: Optional[int] = None
    is_churned: Optional[bool] = None
    onboarding_completed: Optional[bool] = None


class TicketCreate(BaseModel):
    customer_id: str
    title: str
    description: str
    category: Optional[str] = "General"
    priority: Optional[str] = "Medium"
    assigned_agent: Optional[str] = "agent_001"


class TicketStatusUpdate(BaseModel):
    status: str
    csat_score: Optional[int] = None


class AgentQuery(BaseModel):
    customer_id: str
    query: str
    chat_history: Optional[list] = []


class MemoryChat(BaseModel):
    message: str


@app.get("/")
def root():
    return {
        "message": "E-Cell CRM API is running.",
        "docs":    "/docs",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    customers = get_all_customers()
    tickets   = get_all_tickets()
    memory    = get_memory_stats()
    return {
        "status":            "healthy",
        "total_customers":   len(customers),
        "total_tickets":     len(tickets),
        "memory_profiles":   memory["customers_with_memory"],
        "timestamp":         datetime.now().isoformat(),
    }


@app.post("/api/v1/customers")
def create_customer_endpoint(data: CustomerCreate, user=Depends(require_role(["Admin", "Agent", "Supervisor"]))):
    start = time.time()
    try:
        customer = create_customer(data.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "id":               customer["customer_id"],
        "status":           "created",
        "cohort_assignment": customer.get("segment"),
        "agent_id":         user["username"],
        "latency_ms":       round((time.time() - start) * 1000, 2),
        "timestamp":        datetime.now().isoformat(),
    }


@app.get("/api/v1/customers")
def list_customers(user=Depends(get_current_user)):
    customers = get_all_customers()
    return {"total": len(customers), "customers": customers}


@app.get("/api/v1/customers/{customer_id}")
def get_customer_endpoint(customer_id: str, user=Depends(get_current_user)):
    customer = get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found.")
    return customer


@app.put("/api/v1/customers/{customer_id}")
def update_customer_endpoint(customer_id: str, data: CustomerUpdate, user=Depends(require_role(["Admin", "Supervisor"]))):
    updates = {k: v for k, v in data.dict().items() if v is not None}
    try:
        updated = update_customer(customer_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return updated


@app.delete("/api/v1/customers/{customer_id}")
def delete_customer_endpoint(customer_id: str, user=Depends(require_role(["Admin"]))):
    try:
        delete_customer(customer_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "deleted", "customer_id": customer_id}


@app.get("/api/v1/customers/{customer_id}/timeline")
def get_timeline(customer_id: str, user=Depends(get_current_user)):
    timeline = get_customer_timeline(customer_id)
    return {"customer_id": customer_id, "events": timeline}


@app.post("/api/v1/tickets/create")
def create_ticket_endpoint(data: TicketCreate, user=Depends(require_role(["Admin", "Agent", "Supervisor"]))):
    start = time.time()
    try:
        ticket = create_ticket(data.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    routing = route_ticket(ticket)

    return {
        "ticket_id":      ticket["ticket_id"],
        "category":       ticket["category"],
        "assigned_agent": routing["assigned_agent"],
        "status":         routing["new_status"],
        "escalated":      routing["escalated"],
        "agent_id":       user["username"],
        "latency_ms":     round((time.time() - start) * 1000, 2),
        "timestamp":      datetime.now().isoformat(),
    }


@app.get("/api/v1/tickets")
def list_tickets(status: Optional[str] = None, user=Depends(get_current_user)):
    if status:
        tickets = get_tickets_by_status(status)
    else:
        tickets = get_all_tickets()
    return {"total": len(tickets), "tickets": tickets}


@app.get("/api/v1/tickets/{ticket_id}")
def get_ticket_endpoint(ticket_id: str, user=Depends(get_current_user)):
    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")
    return ticket


@app.post("/api/v1/tickets/{ticket_id}/summarize")
def summarize_ticket_endpoint(ticket_id: str, user=Depends(get_current_user)):
    start  = time.time()
    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")

    summary = summarize_ticket(ticket)

    return {
        "ticket_id":        ticket_id,
        "summary":          summary,
        "agent_id":         user["username"],
        "source_confidence": 0.85,
        "latency_ms":       round((time.time() - start) * 1000, 2),
        "timestamp":        datetime.now().isoformat(),
    }


@app.put("/api/v1/tickets/{ticket_id}/status")
def update_ticket_status_endpoint(ticket_id: str, data: TicketStatusUpdate, user=Depends(require_role(["Admin", "Agent", "Supervisor"]))):
    try:
        ticket = update_ticket_status(ticket_id, data.status, data.csat_score)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ticket


@app.post("/api/v1/query/agent")
def query_agent_endpoint(data: AgentQuery, user=Depends(get_current_user)):
    start  = time.time()
    result = query_agent(data.customer_id, data.query, data.chat_history)

    return {
        "answer":     result["answer"],
        "source":     result["source"],
        "confidence": result["confidence"],
        "agent_id":   user["username"],
        "latency_ms": round((time.time() - start) * 1000, 2),
        "timestamp":  datetime.now().isoformat(),
    }


@app.post("/api/v1/customers/{customer_id}/chat")
def chat_with_customer_memory(customer_id: str, data: MemoryChat, user=Depends(get_current_user)):
    start    = time.time()
    customer = get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found.")

    response = chat_with_memory(customer_id, data.message)

    return {
        "customer_id": customer_id,
        "response":    response,
        "agent_id":    user["username"],
        "latency_ms":  round((time.time() - start) * 1000, 2),
        "timestamp":   datetime.now().isoformat(),
    }


@app.get("/api/v1/customers/{customer_id}/memory")
def get_customer_memory(customer_id: str, user=Depends(get_current_user)):
    memory = load_memory(customer_id)
    return memory


@app.get("/api/v1/cohorts/analysis")
def cohort_analysis(user=Depends(require_role(["Admin", "Supervisor", "Analytics"]))):
    start    = time.time()
    analysis = run_full_cohort_analysis()

    return {
        "cohort_id":       "all",
        "total_cohorts":   analysis["total_cohorts"],
        "total_customers": analysis["total_customers"],
        "cohorts":         analysis["cohorts"],
        "latency_ms":      round((time.time() - start) * 1000, 2),
        "timestamp":       datetime.now().isoformat(),
    }


@app.get("/api/v1/cohorts/high-risk")
def high_risk_customers(threshold: float = 0.6, user=Depends(require_role(["Admin", "Supervisor", "Analytics"]))):
    customers = get_high_risk_customers(threshold)
    return {"threshold": threshold, "count": len(customers), "customers": customers}


@app.get("/api/v1/heart")
def heart_scores(user=Depends(require_role(["Admin", "Supervisor", "Analytics"]))):
    start  = time.time()
    scores = compute_heart_scores()

    return {
        "overall_score": scores["overall_score"],
        "happiness":     scores["happiness"],
        "engagement":    scores["engagement"],
        "adoption":      scores["adoption"],
        "retention":     scores["retention"],
        "task_success":  scores["task_success"],
        "latency_ms":    round((time.time() - start) * 1000, 2),
        "timestamp":     datetime.now().isoformat(),
    }


@app.get("/api/v1/crm/stats")
def crm_stats(user=Depends(get_current_user)):
    return get_crm_stats()