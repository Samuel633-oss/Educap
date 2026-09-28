"""Exam Agent: generates one practice question at a time, tuned to mastery."""
import re

from agents.base import format_context, system_prompt
from llm import get_llm

ROLE = """ROLE=exam_generate. Write ONE {qtype} question about the topic at {difficulty} difficulty.
Do not repeat these earlier questions: {recent}.
{focus}
Return JSON: {{"question":"...","type":"mcq|short|problem","options":["A. ..","B. ..","C. ..","D. .."] or [],
"answer":"correct letter for mcq, otherwise a concise model answer","concept":"specific concept tested (2-4 words)",
"explanation":"one-sentence reason"}}"""


def _difficulty(rows: list[dict]) -> tuple[str, str]:
    if not rows:
        return "medium", "Choose a core concept of the topic."
    weakest = rows[0]  # snapshot is sorted weakest-first
    score = weakest["mastery_score"]
    level = "easy" if score < 0.4 else "medium" if score < 0.75 else "hard"
    return level, f"Target this weak concept if sensible: {weakest['concept']}."


def _qtype(message: str, asked: int) -> str:
    low = message.lower()
    if re.search(r"mcq|multiple choice", low): return "multiple-choice"
    if re.search(r"short answer", low): return "short-answer"
    if re.search(r"problem|calculate|solve", low): return "problem-solving"
    return "multiple-choice" if asked % 2 == 0 else "short-answer"


def run(state: dict) -> dict:
    session = dict(state["session"])
    quiz = dict(session.get("quiz") or {"active": True, "asked": 0, "correct": 0, "recent": []})
    quiz["active"] = True
    difficulty, focus = _difficulty(state.get("mastery_information") or [])
    qtype = _qtype(state["current_message"], quiz["asked"])
    system = system_prompt(ROLE.format(qtype=qtype, difficulty=difficulty, focus=focus,
                                       recent="; ".join(quiz["recent"][-4:]) or "none"))
    ctx = format_context(state, mastery=False)
    user = ((f"{ctx}\n\n" if ctx else "") +
            f"Subject: {state.get('current_subject')}. Topic: {state.get('current_topic')}.")
    data = get_llm().ask_json(system, user, tier="strong", max_tokens=700, retries=1)
    prefix = state.get("final_response")
    if isinstance(data, dict) and data.get("question"):
        options = [str(o) for o in (data.get("options") or [])][:5]
        pending = {"question": str(data["question"]), "options": options, "answer": str(data.get("answer") or ""),
                   "concept": str(data.get("concept") or state.get("current_topic") or "general"),
                   "explanation": str(data.get("explanation") or ""), "type": data.get("type", "short")}
        body = f"**Question {quiz['asked'] + 1}** · {difficulty}\n\n{pending['question']}"
        if options:
            body += "\n\n" + "\n".join(f"- {o}" for o in options)
        payload = {"type": "options", "options": options} if options else None
    else:  # model ignored JSON: fall back to a plain question, graded from the model's own knowledge
        text = get_llm().chat([{"role": "system", "content": system_prompt("ROLE=exam_plain. Ask ONE question. Output only the question.")},
                               {"role": "user", "content": user}], tier="strong", max_tokens=250)
        pending = {"question": text, "options": [], "answer": "", "concept": state.get("current_topic") or "general",
                   "explanation": "", "type": "short"}
        body, payload = f"**Question {quiz['asked'] + 1}** · {difficulty}\n\n{text}", None
    quiz["recent"] = (quiz["recent"] + [pending["question"][:80]])[-6:]
    session.update(pending_question=pending, quiz=quiz, hint_level=0)
    text = f"{prefix}\n\n---\n\n{body}" if prefix else body
    return {"final_response": text, "session": session, "payload": payload}
