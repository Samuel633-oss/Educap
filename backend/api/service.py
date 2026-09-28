"""Chat service: loads short-term memory, runs the graph, persists everything.

Yields events so the UI can show 'Tutor Agent is explaining...' while it works.
"""
from typing import Iterator

from sqlalchemy.orm import Session

from graph.workflow import get_graph
from llm import LLMError
from models.tables import Conversation, Message, Student, utcnow

STATUS = {"tutor": "Tutor Agent is explaining…", "socratic": "Socratic Agent is thinking of a hint…",
          "exam": "Exam Agent is preparing a question…", "assessment": "Assessment Agent is checking your answer…",
          "case": "Case Agent is setting up the scenario…", "revision": "Revision Agent is reviewing your progress…",
          "flashcards": "Flashcard Agent is making cards…", "planner": "Planner Agent is building your plan…",
          "research": "Research Agent is searching sources…"}
AGENT_OF = {"teach": "tutor", "chat": "tutor", "socratic": "socratic", "quiz": "exam", "answer": "assessment",
            "assess": "assessment", "revise": "revision", "case": "case", "flashcards": "flashcards",
            "plan": "planner", "research": "research"}


def get_conversation(db: Session, student_id: int, conversation_id: int | None, first_message: str) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if not conv or conv.student_id != student_id:  # isolation
            raise PermissionError("Conversation not found")
        return conv
    conv = Conversation(student_id=student_id, title=first_message[:60], state={})
    db.add(conv)
    db.commit()
    return conv


def chat_stream(db: Session, student_id: int, message: str, conversation_id: int | None = None) -> Iterator[dict]:
    if not db.get(Student, student_id):
        raise LookupError("Student not found")
    conv = get_conversation(db, student_id, conversation_id, message)
    history = [{"role": m.role, "content": m.content} for m in
               db.query(Message).filter_by(conversation_id=conv.id).order_by(Message.id.desc()).limit(8).all()][::-1]
    db.add(Message(conversation_id=conv.id, role="user", content=message))
    db.commit()
    state = {"student_id": student_id, "conversation_id": conv.id, "current_message": message,
             "conversation_history": history, "session": dict(conv.state or {}), "trace": []}
    try:
        for update in get_graph().stream(state, {"configurable": {"db": db}}, stream_mode="updates"):
            for node, out in update.items():
                state.update(out)
                if node == "supervisor":
                    yield {"type": "status", "agent": AGENT_OF.get(out["intent"], "tutor"),
                           "label": STATUS[AGENT_OF.get(out["intent"], "tutor")]}
                elif node == "assessment" and out.get("next_action") == "exam_next":
                    yield {"type": "status", "agent": "exam", "label": STATUS["exam"]}
        reply, agent = state.get("final_response") or "Hmm, I have nothing to say - try rephrasing?", state.get("current_agent", "tutor")
    except LLMError as e:
        reply, agent = (f"⚠️ I couldn't reach the AI model ({e}). Free models are often rate-limited - "
                        "please try again in a moment."), "system"
    payload = state.get("payload")
    if state.get("mastery_update"):
        payload = {**(payload or {}), "mastery_update": state["mastery_update"]}
    db.add(Message(conversation_id=conv.id, role="assistant", content=reply, agent=agent, payload=payload))
    conv.state, conv.updated_at = state.get("session", conv.state), utcnow()
    db.commit()
    yield {"type": "final", "conversation_id": conv.id, "reply": reply, "agent": agent,
           "intent": state.get("intent"), "subject": state.get("current_subject"),
           "topic": state.get("current_topic"), "payload": payload, "trace": state.get("trace", [])}


def chat_once(db: Session, student_id: int, message: str, conversation_id: int | None = None) -> dict:
    final = {}
    for ev in chat_stream(db, student_id, message, conversation_id):
        final = ev
    return final
