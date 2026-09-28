import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents import mastery as mastery_agent
from api.service import chat_once, chat_stream
from config import settings
from database.db import get_db
from memory.storage import delete_memory, list_memories
from models.tables import Conversation, Document, Message, Student
from rag.ingestion import delete_document, extract_text, ingest_text
from tools.builtin import TOOLS

router = APIRouter(prefix="/api")


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str | None = None


class ChatIn(BaseModel):
    student_id: int
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class TextDocIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=10)
    subject: str = "General"


def _student(db: Session, student_id: int) -> Student:
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    return s


@router.get("/health")
def health():
    return {"ok": True, "llm_configured": bool(settings.openrouter_api_key), "model": settings.strong_model}


@router.get("/tools")
def tools():
    return [{"name": t.name, "description": t.description} for t in TOOLS.values()]


@router.post("/students")
def create_student(body: StudentIn, db: Session = Depends(get_db)):
    s = Student(name=body.name.strip(), email=body.email)
    db.add(s)
    db.commit()
    return {"id": s.id, "name": s.name}


@router.post("/chat")
def chat(body: ChatIn, db: Session = Depends(get_db)):
    try:
        return chat_once(db, body.student_id, body.message, body.conversation_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.post("/chat/stream")
def chat_stream_endpoint(body: ChatIn, db: Session = Depends(get_db)):
    _student(db, body.student_id)
    if body.conversation_id:
        conv = db.get(Conversation, body.conversation_id)
        if not conv or conv.student_id != body.student_id:
            raise HTTPException(403, "Conversation not found")

    def gen():
        try:
            for ev in chat_stream(db, body.student_id, body.message, body.conversation_id):
                yield json.dumps(ev) + "\n"
        except Exception as e:  # never leave the UI hanging
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.get("/students/{student_id}/conversations")
def conversations(student_id: int, db: Session = Depends(get_db)):
    _student(db, student_id)
    rows = db.query(Conversation).filter_by(student_id=student_id).order_by(Conversation.updated_at.desc()).limit(30).all()
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()} for c in rows]


@router.get("/students/{student_id}/conversations/{conversation_id}")
def conversation_messages(student_id: int, conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.student_id != student_id:
        raise HTTPException(404, "Conversation not found")
    msgs = db.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.id).all()
    return [{"role": m.role, "content": m.content, "agent": m.agent, "payload": m.payload} for m in msgs]


@router.get("/students/{student_id}/mastery")
def mastery(student_id: int, db: Session = Depends(get_db)):
    _student(db, student_id)
    return mastery_agent.snapshot(db, student_id, limit=100)


@router.get("/students/{student_id}/memories")
def memories(student_id: int, db: Session = Depends(get_db)):
    _student(db, student_id)
    return [{"id": m.id, "type": m.memory_type, "content": m.content, "importance": m.importance}
            for m in list_memories(db, student_id)]


@router.delete("/students/{student_id}/memories/{memory_id}")
def remove_memory(student_id: int, memory_id: int, db: Session = Depends(get_db)):
    if not delete_memory(db, student_id, memory_id):
        raise HTTPException(404, "Memory not found")
    return {"ok": True}


@router.get("/students/{student_id}/documents")
def documents(student_id: int, db: Session = Depends(get_db)):
    _student(db, student_id)
    rows = db.query(Document).filter_by(student_id=student_id).order_by(Document.created_at.desc()).all()
    return [{"id": d.id, "title": d.title, "subject": d.subject, "chunks": d.chunk_count, "source": d.source} for d in rows]


@router.post("/students/{student_id}/documents")
def add_text_document(student_id: int, body: TextDocIn, db: Session = Depends(get_db)):
    _student(db, student_id)
    try:
        d = ingest_text(db, student_id, body.title, body.text, body.subject)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": d.id, "title": d.title, "chunks": d.chunk_count}


@router.post("/students/{student_id}/documents/upload")
async def upload_document(student_id: int, file: UploadFile = File(...), subject: str = Form("General"),
                          db: Session = Depends(get_db)):
    _student(db, student_id)
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 8 MB)")
    try:
        text = extract_text(file.filename or "notes.txt", data)
        d = ingest_text(db, student_id, file.filename or "Uploaded notes", text, subject, source=file.filename or "upload")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": d.id, "title": d.title, "chunks": d.chunk_count}


@router.delete("/students/{student_id}/documents/{document_id}")
def remove_document(student_id: int, document_id: int, db: Session = Depends(get_db)):
    if not delete_document(db, student_id, document_id):
        raise HTTPException(404, "Document not found")
    return {"ok": True}
