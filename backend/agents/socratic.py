"""Socratic Agent: guides with questions and graded hints instead of answers."""
from agents.base import chat, format_context, system_prompt

ROLE = """ROLE=socratic. You never hand over the final answer straight away. Ask ONE guiding question or give ONE hint,
then wait. Hint level {level}: 1 = a probing question about the first step; 2 = a stronger nudge naming the
relevant idea; 3 = a near-complete hint that leaves the last step to the student; 4+ = the student has tried
enough: explain the full answer kindly. Gently challenge wrong assumptions and name likely misconceptions. Max 90 words."""


def run(state: dict) -> dict:
    session = dict(state["session"])
    level = int(session.get("hint_level", 0)) + 1
    pending = session.get("pending_question")
    ctx = format_context(state, mastery=False)
    if pending:
        target = (f"Question the student is working on: {pending['question']}\n"
                  f"Reference answer (NEVER reveal before hint level 4): {pending.get('answer') or 'unknown'}")
    else:
        target = "The student is working on something from the recent conversation (see history)."
    user = (f"{ctx}\n\n" if ctx else "") + f"{target}\nStudent says: {state['current_message']}"
    reply = chat(system_prompt(ROLE.format(level=level)), user, state, history=6)
    session["hint_level"] = level
    if level >= 4:
        session["hint_level"], session["pending_question"] = 0, None
    return {"final_response": reply, "session": session}
