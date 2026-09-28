"""Memory extraction: decide what is worth remembering long-term.

Two cheap gates keep costs down:
 1. should_extract(): a regex check - most messages ("explain X") contain nothing durable.
 2. the LLM call uses the fast tier and must return a strict JSON list.
"""
import re

from sqlalchemy.orm import Session

from llm import LLMError, get_llm
from memory.storage import TYPES, add_memory

SIGNAL = re.compile(
    r"\b(i prefer|i like|i love|i want|i need|i am|i'm|i study|i learn|i struggle|i find|i keep|"
    r"i always|i usually|i never|my (goal|exam|course|level|major|class|weakness|strength)|"
    r"simpler|simple words|too (fast|hard|difficult|complicated|easy)|beginner|advanced|intermediate|"
    r"don'?t understand|do not understand|confus|struggl|preparing|studying|learning|"
    r"exam (on|in)|test (on|in)|examples? first|step by step|analog)", re.I)

PROMPT = """ROLE=memory_extractor. From the student's message, extract DURABLE learning facts worth
remembering across future conversations: preferences (explanation style), goals/exams, current level,
recurring struggles, strengths, misconceptions. Ignore the question itself and one-off requests.
Return JSON: {"facts":[{"content":"third-person fact, max 20 words","type":"preference|goal|level|struggle|strength|misconception|context","importance":0.0-1.0}]}
Return {"facts":[]} if nothing durable. At most 3 facts."""


def should_extract(message: str) -> bool:
    return bool(SIGNAL.search(message or ""))


def extract_facts(message: str, topic: str | None = None) -> list[dict]:
    try:
        data = get_llm().ask_json(PROMPT, f"Current topic: {topic or 'unknown'}\nStudent said: {message[:600]}",
                                  tier="fast")
    except LLMError:
        return []
    facts = (data or {}).get("facts", []) if isinstance(data, dict) else []
    out = []
    for f in facts[:3]:
        if isinstance(f, dict) and isinstance(f.get("content"), str):
            t = f.get("type", "context")
            out.append({"content": f["content"], "type": t if t in TYPES else "context",
                        "importance": float(f.get("importance", 0.5) or 0.5)})
    return out


def extract_and_store(db: Session, student_id: int, message: str, topic: str | None = None) -> list[str]:
    if not should_extract(message):
        return []
    stored = []
    for f in extract_facts(message, topic):
        if add_memory(db, student_id, f["content"], f["type"], f["importance"]):
            stored.append(f["content"])
    return stored
