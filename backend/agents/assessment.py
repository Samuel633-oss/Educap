"""Assessment Agent: grades answers, spots misconceptions, produces progress reports.

MCQs with an answer key are graded in plain Python (reliable, free); the LLM only
writes the explanation. Free-text answers are graded by the LLM as strict JSON.
"""
import re

from agents.base import chat, format_context, system_prompt
from agents import mastery as mastery_agent
from llm import get_llm

QUIZ_LENGTH = 5
JSON_ROLE = """ROLE=assessment_grade. Grade the student's answer fairly (accept equivalent wording).
Return JSON: {"correct":true|false,"score":0.0-1.0,"concept":"concept tested","misconception":"short text or null","feedback":"2-3 kind sentences: what was right/wrong and the key idea"}"""
TEXT_ROLE = "ROLE=assessment_feedback. The student's answer was {verdict}. In 2-3 kind sentences explain why the correct answer is right and, if wrong, the likely misconception."


def _letter(answer: str, options: list[str]) -> str | None:
    m = re.match(r"^\W*([A-Ea-e])\b", answer.strip())
    if m:
        return m.group(1).upper()
    for o in options:
        body = re.sub(r"^[A-E][.)]\s*", "", o).strip().lower()
        if body and body == answer.strip().lower():
            return o[0].upper()
    return None


def _confidence(answer: str) -> str:
    return "low" if re.search(r"\b(guess|not sure|maybe|i think|no idea|don'?t know)\b", answer, re.I) else "normal"


def _evaluate(state: dict, pending: dict, answer: str) -> dict:
    key = re.match(r"^\W*([A-Ea-e])\b", pending.get("answer") or "")
    letter = _letter(answer, pending.get("options", [])) if pending.get("options") and key else None
    if letter:
        correct = letter == key.group(1).upper()
        feedback = chat(system_prompt(TEXT_ROLE.format(verdict="correct" if correct else "incorrect")),
                        f"Question: {pending['question']}\nOptions: {pending['options']}\nCorrect: {pending['answer']}\n"
                        f"Student chose: {letter}\nHint: {pending.get('explanation')}", tier="fast", max_tokens=250)
        return {"correct": correct, "score": 1.0 if correct else 0.0, "concept": pending["concept"],
                "misconception": None, "feedback": feedback}
    user = (f"Question: {pending['question']}\nReference answer: {pending.get('answer') or '(none - use your own knowledge)'}\n"
            f"Student answer: {answer}")
    data = get_llm().ask_json(system_prompt(JSON_ROLE), user, tier="strong", max_tokens=400, retries=1)
    if isinstance(data, dict) and "correct" in data:
        return {"correct": bool(data["correct"]), "score": float(data.get("score", 1.0 if data["correct"] else 0.0)),
                "concept": str(data.get("concept") or pending["concept"]),
                "misconception": data.get("misconception") if data.get("misconception") not in (None, "null", "") else None,
                "feedback": str(data.get("feedback") or "")}
    feedback = chat(system_prompt("ROLE=assessment_feedback. Give brief, kind feedback on the answer."), user, tier="fast", max_tokens=250)
    return {"correct": None, "score": None, "concept": pending["concept"], "misconception": None, "feedback": feedback}


def report(rows: list[dict]) -> str:
    if not rows:
        return "I don't have any recorded results yet."
    strong, weak = mastery_agent.strengths_and_weaknesses(rows)
    lines = ["**Your progress**"]
    if strong:
        lines.append("\n**Strong**\n" + "\n".join(f"- {r['concept']} ({round(r['mastery_score']*100)}%)" for r in strong))
    if weak:
        lines.append("\n**Needs improvement**\n" + "\n".join(f"- {r['concept']} ({round(r['mastery_score']*100)}%)" for r in weak))
    mid = [r for r in rows if r not in strong and r not in weak]
    if mid:
        lines.append("\n**Getting there**\n" + "\n".join(f"- {r['concept']} ({round(r['mastery_score']*100)}%)" for r in mid))
    return "\n".join(lines)


def run(state: dict) -> dict:
    session = dict(state["session"])
    # --- mode 1: progress report (assess intent / stop quiz) ---
    if state["intent"] == "assess":
        text = report(state.get("mastery_information") or [])
        quiz = dict(session.get("quiz") or {})
        if state.get("next_action") == "report_only":
            session.update(pending_question=None, quiz={**quiz, "active": False})
            return {"final_response": text + "\n\nNice work. Ask me to quiz you whenever you want more practice.",
                    "session": session, "next_action": "none"}
        text += "\n\nLet's run a quick diagnostic to sharpen this picture."
        return {"final_response": text, "session": session, "next_action": "exam_next"}
    # --- mode 2: grade the student's answer ---
    pending = session.get("pending_question")
    if not pending:
        return {"final_response": "Ask me for a quiz and I'll set a question for you first.", "session": session}
    answer = state["current_message"]
    result = _evaluate(state, pending, answer)
    result["confidence"] = _confidence(answer)
    mark = {True: "✅ **Correct!**", False: "❌ **Not quite.**", None: "📝 **Feedback**"}[result["correct"]]
    text = f"{mark} {result['feedback']}"
    if result["misconception"]:
        text += f"\n\n*Watch out:* {result['misconception']}"
    quiz = dict(session.get("quiz") or {"active": False, "asked": 0, "correct": 0, "recent": []})
    quiz["asked"] = quiz.get("asked", 0) + 1
    quiz["correct"] = quiz.get("correct", 0) + (1 if result["correct"] else 0)
    session.update(pending_question=None, hint_level=0)
    nxt = "none"
    if quiz.get("active"):
        if quiz["asked"] < QUIZ_LENGTH:
            nxt = "exam_next"
        else:
            text += f"\n\n🏁 **Round complete: {quiz['correct']}/{quiz['asked']} correct.**"
            quiz["active"] = False
            quiz["asked"] = quiz["correct"] = 0
    session["quiz"] = quiz
    return {"final_response": text, "session": session, "assessment": result, "student_answer": answer, "next_action": nxt}
