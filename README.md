# E-Cell NIT Trichy — Task 3: AI-Integrated CRM Platform

An end-to-end AI-native CRM platform built for E-Cell NIT Trichy's AI & Automation domain recruitment task.

## What It Does

A full CRM system that manages customers and support tickets with AI-powered features including ticket summarization, agent workflows, interaction memory, cohort analysis, and a HEART framework dashboard.

## Project Structure

project/
├── data/
├── src/
│   ├── crm.py
│   ├── agents.py
│   ├── memory.py
│   ├── cohort.py
│   └── heart.py
├── api/
│   └── app.py
├── models/
├── generate_data.py
├── requirements.txt
└── README.md

## Modules

**Module 1 — crm.py**
Customer and ticket management with full CRUD, lifecycle state transitions, customer segmentation, and timeline views.

**Module 2 — agents.py**
LangChain-style ticket summarization, LangGraph-style agent workflow with automatic routing, escalation, and AI-generated suggested responses using Gemini.

**Module 3 — memory.py**
Per-customer short-term and long-term memory buffers. Cross-session chat history retrieval and memory-aware response generation.

**Module 4 — cohort.py**
Customer cohort segmentation by acquisition date and plan. Retention curve computation, churn scoring, and high-risk customer identification.

**Module 5 — heart.py**
Full HEART framework metric computation:
- H — Happiness: CSAT and NPS scores
- E — Engagement: Weekly active users and session depth
- A — Adoption: Onboarding rate and feature usage
- R — Retention: Monthly retention curves and churn rate
- T — Task Success: Ticket resolution and first-contact rates

**Module 6 — api/app.py**
Production FastAPI backend with role-based access control, versioned endpoints under /api/v1/, and auto-generated Swagger docs at /docs.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/customers | Create customer |
| GET | /api/v1/customers | List all customers |
| GET | /api/v1/customers/{id} | Get customer |
| PUT | /api/v1/customers/{id} | Update customer |
| DELETE | /api/v1/customers/{id} | Delete customer |
| GET | /api/v1/customers/{id}/timeline | Customer timeline |
| POST | /api/v1/tickets/create | Create ticket |
| POST | /api/v1/tickets/{id}/summarize | AI summarize ticket |
| PUT | /api/v1/tickets/{id}/status | Update ticket status |
| POST | /api/v1/query/agent | Query AI agent |
| POST | /api/v1/customers/{id}/chat | Chat with memory |
| GET | /api/v1/cohorts/analysis | Full cohort analysis |
| GET | /api/v1/cohorts/high-risk | High risk customers |
| GET | /api/v1/heart | HEART framework scores |
| GET | /api/v1/crm/stats | CRM statistics |

## Roles

| Username | Password | Access |
|----------|----------|--------|
| admin | admin123 | Full access |
| agent | agent123 | Tickets and queries |
| supervisor | supervisor123 | Most endpoints |
| analytics | analytics123 | Read-only, cohorts and HEART |

## Dataset

500 synthetic customer profiles and 1000 support tickets generated using Gemini API, covering 6 months of interaction history across 8 industries and 4 subscription plans.

## Evaluation Metrics

- HEART Scores computed from live CRM data
- Cohort retention curves across 6 months
- Churn prediction scores per customer
- Ticket resolution rate and first-contact rate
- Agent response latency per endpoint