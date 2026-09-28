"""Shared helpers for all agents: system prompt, context formatting, LLM call."""
from llm import get_llm

SAFETY = ("Safety rules: you are an educational tutor, not a doctor, lawyer or financial advisor. "
          "Never diagnose real people or prescribe medication; clinical content is educational only and "
          "real health concerns need a qualified professional. Encourage learning: guide the student "
          "rather than silently doing their graded work, but never be evasive when they need a clear explanation.")


def system_prompt(role: str) -> str:
    return ("You are part of Educap, a friendly team of AI tutors for students of any subject.\n"
            f"{role}\n{SAFETY}\nWrite in clear Markdown. Use $...$ for inline math. Be concise and warm.")


def history_messages(state: dict, n: int = 6) -> list[dict]:
    return [{"role": m["role"], "content": m["content"][:700]}
            for m in state.get("conversation_history", [])[-n:]]


def format_context(state: dict, memories=True, docs=True, mastery=True) -> str:
    """Turn ONLY the already-retrieved, relevant items into a compact prompt block."""
    parts = []
    if memories and state.get("retrieved_memories"):
        parts.append("What we know about this student:\n" + "\n".join(f"- {m}" for m in state["retrieved_memories"]))
    if docs and state.get("retrieved_documents"):
        parts.append("Excerpts from the student's own study material (use them and mention the title):\n" +
                     "\n".join(f"[{d['title']}] {d['content'][:700]}" for d in state["retrieved_documents"]))
    if mastery and state.get("mastery_information"):
        parts.append("Mastery so far:\n" + "\n".join(
            f"- {m['concept']}: {round(m['mastery_score'] * 100)}% ({m['attempts']} attempts)"
            for m in state["mastery_information"]))
    return "\n\n".join(parts)


def chat(system: str, user: str, state: dict | None = None, history: int = 0,
         tier: str = "strong", **kw) -> str:
    msgs = [{"role": "system", "content": system}]
    if state and history:
        msgs += history_messages(state, history)
    msgs.append({"role": "user", "content": user})
    return get_llm().chat(msgs, tier=tier, **kw)
