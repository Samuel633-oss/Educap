"""Flashcard Agent: turns a topic (and the student's notes, if any) into flip-cards."""
from tools.builtin import call_tool


def run(state: dict) -> dict:
    topic = state.get("current_topic") or "this topic"
    notes = "\n\n".join(d["content"] for d in state.get("retrieved_documents") or [])
    cards = call_tool("flashcard_generator", topic=topic, context=notes, n=6)
    if not cards:
        return {"final_response": "I couldn't generate flashcards just now. Try again in a moment."}
    src = " from your notes" if notes else ""
    return {"final_response": f"Here are **{len(cards)} flashcards{src}** on **{topic}**. Tap a card to flip it.",
            "payload": {"type": "flashcards", "cards": cards}}
