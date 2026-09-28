import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..database.db import SessionLocal, Student, Conversation, Message
from ..graph.workflow import build_graph
from ..llm import get_llm

router = APIRouter(prefix="/api")
_graph = None
def graph():
    global _graph
    _graph = _graph or build_graph(get_llm())
    return _graph

class ChatIn(BaseModel):
    student_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None

class ChatOut(BaseModel):
    conversation_id: str
    agent: str
    reply: str

@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn):
    with SessionLocal() as db:
        if not db.get(Student, body.student_id):
            db.add(Student(id=body.student_id)); db.commit()
        conv = db.get(Conversation, body.conversation_id) if body.conversation_id else None
        # Isolation: a conversation must belong to the student asking.
        if conv and conv.student_id != body.student_id:
            raise HTTPException(403, "Conversation not found")
        if not conv:
            conv = Conversation(id=str(uuid.uuid4()), student_id=body.student_id)
            db.add(conv); db.commit()
        rows = (db.query(Message).filter_by(conversation_id=conv.id)
                .order_by(Message.id.desc()).limit(8).all())[::-1]
        history = [{"role": r.role, "content": r.content} for r in rows]
        last_agent = next((r.agent for r in reversed(rows) if r.agent), "")

        try:
            out = await graph().ainvoke({
                "student_id": body.student_id, "conversation_id": conv.id,
                "current_message": body.message, "conversation_history": history,
                "last_agent": last_agent})
        except Exception as e:
            raise HTTPException(502, f"The tutor could not answer: {e}")

        db.add(Message(conversation_id=conv.id, role="user", content=body.message))
        db.add(Message(conversation_id=conv.id, role="assistant",
                       content=out["final_response"], agent=out["current_agent"]))
        db.commit()
        return ChatOut(conversation_id=conv.id, agent=out["current_agent"], reply=out["final_response"])
