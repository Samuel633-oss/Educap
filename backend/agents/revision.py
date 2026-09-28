"""Revision Agent: ranks what to review using mastery + time since last review."""
from datetime import datetime

from agents.base import chat, format_context, system_prompt
from models.tables import utcnow

ROLE = """ROLE=revision. Build a short, motivating revision plan from the ranked list. For each item (max 5):
what to review (1 line) and one quick tip. Mention that they can say "quiz me on <concept>" to practise.
Address the student directly. Do not invent items that are not in the list."""


def priority(row: dict, now: datetime) -> float:
    days = 14.0
    if row.get("last_reviewed"):
        days = (now - datetime.fromisoformat(row["last_reviewed"])).total_seconds() / 86400
    staleness = min(days / 7, 1.0)  # a week without review = fully stale
    return 0.7 * (1 - row["mastery_score"]) + 0.3 * staleness


def rank(rows: list[dict]) -> list[dict]:
    now = utcnow()
    return sorted(rows, key=lambda r: priority(r, now), reverse=True)


def run(state: dict) -> dict:
    rows = rank(state.get("mastery_information") or [])[:5]
    if not rows:
        return {"final_response": "I don't have any practice results yet, so there's nothing to revise. "
                                  "Ask me to teach you something and then say *quiz me* - I'll track what needs work."}
    now = utcnow()
    lines = []
    for r in rows:
        days = "never" if not r["last_reviewed"] else f"{(now - datetime.fromisoformat(r['last_reviewed'])).days}d ago"
        lines.append(f"- {r['concept']} (topic: {r['topic']}) mastery {round(r['mastery_score']*100)}%, "
                     f"last practised {days}, {r['incorrect_answers']} wrong of {r['attempts']}")
    ctx = format_context(state, docs=False, mastery=False)
    reply = chat(system_prompt(ROLE), (f"{ctx}\n\n" if ctx else "") + "Ranked review list:\n" + "\n".join(lines), tier="strong", max_tokens=500)
    return {"final_response": reply}
