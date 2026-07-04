import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()

MEMORY_DIR = Path("models/memory")
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = Path("data")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL  = "gemini-2.0-flash"


def load_json(path: Path):
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_memory_path(customer_id: str) -> Path:
    return MEMORY_DIR / f"{customer_id}.json"


def load_memory(customer_id: str) -> dict:
    path = get_memory_path(customer_id)

    if not path.exists():
        return {
            "customer_id":   customer_id,
            "short_term":    [],
            "long_term":     [],
            "summary":       None,
            "last_updated":  None,
        }

    with open(path) as f:
        return json.load(f)


def save_memory(memory: dict):
    customer_id = memory["customer_id"]
    path        = get_memory_path(customer_id)
    memory["last_updated"] = datetime.now().isoformat()

    with open(path, "w") as f:
        json.dump(memory, f, indent=2)


def add_to_short_term(customer_id: str, role: str, content: str):
    memory = load_memory(customer_id)

    memory["short_term"].append({
        "role":      role,
        "content":   content,
        "timestamp": datetime.now().isoformat(),
    })

    if len(memory["short_term"]) > 10:
        overflow       = memory["short_term"][:-10]
        memory["short_term"] = memory["short_term"][-10:]
        memory["long_term"].extend(overflow)

    save_memory(memory)


def add_to_long_term(customer_id: str, event: str, details: str):
    memory = load_memory(customer_id)

    memory["long_term"].append({
        "event":     event,
        "details":   details,
        "timestamp": datetime.now().isoformat(),
    })

    save_memory(memory)


def get_short_term_context(customer_id: str, last_n: int = 6) -> list:
    memory = load_memory(customer_id)
    return memory["short_term"][-last_n:]


def get_full_context(customer_id: str) -> str:
    memory  = load_memory(customer_id)
    tickets = load_json(DATA_DIR / "tickets.json")
    logs    = load_json(DATA_DIR / "interaction_logs.json")

    customer_tickets = [t for t in tickets if t["customer_id"] == customer_id][-5:]
    customer_logs    = [l for l in logs    if l["customer_id"] == customer_id][-5:]

    short_term_text = ""
    for msg in memory["short_term"][-6:]:
        short_term_text += f"{msg['role'].upper()}: {msg['content']}\n"

    long_term_text = ""
    for event in memory["long_term"][-5:]:
        long_term_text += f"[{event['timestamp'][:10]}] {event['event']}: {event['details']}\n"

    context = f"""
SHORT TERM MEMORY (recent chat):
{short_term_text if short_term_text else 'No recent chat history.'}

LONG TERM MEMORY (past events):
{long_term_text if long_term_text else 'No long term memory yet.'}

RECENT TICKETS:
{json.dumps(customer_tickets, indent=2)}

RECENT INTERACTIONS:
{json.dumps(customer_logs, indent=2)}
""".strip()

    return context


def summarize_memory(customer_id: str) -> str:
    memory  = load_memory(customer_id)
    context = get_full_context(customer_id)

    if not memory["short_term"] and not memory["long_term"]:
        return "No memory available for this customer yet."

    prompt = f"""Summarize the following customer interaction history into 3-4 concise sentences.
Focus on: key issues raised, sentiment, resolution status, and any patterns.

{context}

Summary:"""

    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        summary  = response.text.strip()
    except Exception:
        summary = "Summary unavailable due to API limit. Check interaction logs directly."

    memory["summary"] = summary
    save_memory(memory)
    return summary


def chat_with_memory(customer_id: str, user_message: str) -> str:
    add_to_short_term(customer_id, "user", user_message)

    context = get_full_context(customer_id)

    prompt = f"""You are a CRM assistant with memory of this customer's history.
Use the context below to answer the agent's message. Be concise and factual.
Only use information from the provided context.

CUSTOMER CONTEXT:
{context}

Agent message: {user_message}

Response:"""

    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        answer   = response.text.strip()
    except Exception:
        answer = "I'm unable to process this right now due to API limits. Please try again shortly."

    add_to_short_term(customer_id, "assistant", answer)
    return answer


def clear_memory(customer_id: str):
    path = get_memory_path(customer_id)
    if path.exists():
        path.unlink()
    return True


def get_memory_stats() -> dict:
    memory_files = list(MEMORY_DIR.glob("*.json"))
    return {
        "customers_with_memory": len(memory_files),
        "memory_dir":            str(MEMORY_DIR),
    }


if __name__ == "__main__":
    customers = load_json(DATA_DIR / "customers.json")

    if customers:
        test_id = customers[0]["customer_id"]
        print(f"\nTesting memory for customer: {test_id}")

        add_to_long_term(test_id, "onboarding", "Customer completed onboarding on day 3")
        add_to_long_term(test_id, "complaint",  "Customer complained about billing in month 2")

        response = chat_with_memory(test_id, "What issues has this customer had before?")
        print(f"\nAgent response:\n{response}")

        summary = summarize_memory(test_id)
        print(f"\nMemory summary:\n{summary}")

        print(f"\nStats: {get_memory_stats()}")