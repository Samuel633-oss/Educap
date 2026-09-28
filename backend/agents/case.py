"""Case/Simulation Agent: text-based interactive scenarios for any subject.

Medicine -> patient case. Programming -> debugging scenario. Business -> business case.
The scenario's hidden facts live in the session (server-side), so the agent can
reveal information gradually as the student asks good questions.
"""
import re

from agents.base import chat, format_context, system_prompt
from llm import get_llm

START_ROLE = """ROLE=case_start. Create an interactive {kind} for a student on the topic. Educational simulation only.
Output exactly two parts separated by a line containing only ###HIDDEN###
PART 1 (visible): a short opening vignette (max 120 words) with only the initial information, then ask what the student would like to do or ask first.
PART 2 (hidden, for you): the underlying answer (e.g. diagnosis/root cause), 4-6 key facts to reveal only when asked or earned, and the ideal reasoning path."""
CONTINUE_ROLE = """ROLE=case_continue. You run a step-by-step {kind}. Stay in role and respond ONLY to what the student asked/did:
reveal a fact only if they asked for it or an action would produce it; otherwise say what is not available yet.
Give a little new information each turn (max 100 words) and ask what they do next.
Do not give the answer. If the student commits to a final answer/decision, or asks to end, or turn {turn} >= 8:
give a short evaluation of their reasoning (what they did well, what they missed, the answer), then on the LAST line write
[[CASE_COMPLETE score=0.0-1.0 concept="reasoning skill or topic"]]"""
MEDICAL = re.compile(r"medic|clinic|anatom|physiolog|patholog|nurs|pharma|cardio|disease|patient|surgery|health", re.I)
DISCLAIMER = "\n\n> *Educational simulation — not real medical advice.*"


def _kind(subject: str, topic: str) -> str:
    text = f"{subject} {topic}"
    if MEDICAL.search(text): return "patient case"
    if re.search(r"program|comput|code|software|python|java|algorithm", text, re.I): return "debugging scenario"
    if re.search(r"business|market|econom|financ|manage|account", text, re.I): return "business case"
    if re.search(r"engineer|electric|mechanic|civil|circuit", text, re.I): return "engineering scenario"
    if re.search(r"chem|physic|biolog|lab|science", text, re.I): return "laboratory scenario"
    return "practical scenario"


def run(state: dict) -> dict:
    session = dict(state["session"])
    case = session.get("active_case")
    ctx = format_context(state, mastery=False)
    if not case:
        subject, topic = state.get("current_subject") or "General", state.get("current_topic") or "general practice"
        kind = _kind(subject, topic)
        raw = get_llm().chat([{"role": "system", "content": system_prompt(START_ROLE.format(kind=kind))},
                              {"role": "user", "content": (f"{ctx}\n\n" if ctx else "") + f"Subject: {subject}. Topic: {topic}."}],
                             tier="strong", max_tokens=800)
        visible, _, hidden = raw.partition("###HIDDEN###")
        visible = visible.replace("PART 1", "").strip(" \n:-*")
        if kind == "patient case":
            visible += DISCLAIMER
        session["active_case"] = {"kind": kind, "topic": topic, "subject": subject, "turn": 0, "hidden": hidden.strip()[:1500]}
        return {"final_response": f"🩺 **{kind.title()}: {topic}**\n\n{visible}" if kind == "patient case"
                else f"🧩 **{kind.title()}: {topic}**\n\n{visible}", "session": session}
    case = dict(case)
    case["turn"] += 1
    end_note = "The student asked to end the case now.\n" if state.get("next_action") == "end" else ""
    user = (f"Scenario secrets (never reveal unearned): {case['hidden']}\n\n{end_note}Student: {state['current_message']}")
    raw = chat(system_prompt(CONTINUE_ROLE.format(kind=case["kind"], turn=case["turn"])), user, state, history=8, max_tokens=600)
    m = re.search(r"\[\[CASE_COMPLETE\s+score=([\d.]+)(?:\s+concept=\"([^\"]*)\")?\]\]", raw)
    text = re.sub(r"\[\[CASE_COMPLETE.*?\]\]", "", raw).strip()
    update: dict = {"final_response": text}
    if m:
        score = max(0.0, min(1.0, float(m.group(1))))
        concept = (m.group(2) or f"{case['topic']} reasoning")[:100]
        update["assessment"] = {"correct": score >= 0.6, "score": score, "concept": concept, "misconception": None,
                                "feedback": "", "confidence": "normal"}
        session["active_case"] = None
        update["final_response"] = text + "\n\n🏁 **Case complete.** Ask for another case or a quiz anytime."
    else:
        session["active_case"] = case
    update["session"] = session
    return update
