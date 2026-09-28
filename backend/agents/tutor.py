"""Tutor Agent: explains concepts, adapting to the student's level and memories."""
from agents.base import chat, format_context, system_prompt
from tools.builtin import calculator, find_arithmetic

ROLE = """ROLE=tutor. You teach. Explain clearly at the student's level (infer it from memories; default to
beginner-friendly). Break the idea into small steps, use one concrete example or analogy, and point out a
common misconception. If study-material excerpts are provided, ground your explanation in them and mention
the title. Keep it under ~300 words. End with ONE short question that checks understanding, then offer to
quiz them or go deeper."""


def run(state: dict) -> dict:
    ctx = format_context(state)
    expr = find_arithmetic(state["current_message"])
    verified = calculator(expr) if expr else None
    user = (f"{ctx}\n\n" if ctx else "") + \
           (f"Verified calculation ({expr} = {verified}). Use this exact value.\n\n" if verified else "") + \
           f"Subject: {state.get('current_subject')}. Topic: {state.get('current_topic')}.\nStudent: {state['current_message']}"
    reply = chat(system_prompt(ROLE), user, state, history=6)
    session = dict(state["session"])
    session["last_taught"] = state.get("current_topic")
    return {"final_response": reply, "session": session}
