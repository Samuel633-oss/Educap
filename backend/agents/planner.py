"""Planner Agent: builds a realistic study schedule from goals, mastery and time available."""
from agents.base import chat, format_context, system_prompt

ROLE = """ROLE=planner. Create a realistic study plan (day-by-day or week-by-week, whichever fits the time the
student mentions; if none, assume 1 week, 45 min/day). Prioritise weak concepts, include short practice/quiz
sessions and spaced review. Use a compact Markdown list. End by asking whether to adjust it."""


def run(state: dict) -> dict:
    ctx = format_context(state, docs=False)
    user = (f"{ctx}\n\n" if ctx else "") + f"Topic/subject: {state.get('current_topic') or state.get('current_subject')}\nRequest: {state['current_message']}"
    return {"final_response": chat(system_prompt(ROLE), user, state, history=2, max_tokens=700)}
