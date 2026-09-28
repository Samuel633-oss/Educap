"""Long-term learner memory storage (with de-duplication)."""
import re

from sqlalchemy.orm import Session

from models.tables import Memory, utcnow
from rag.embeddings import cosine_scores, embed_one

TYPES = {"preference", "goal", "level", "struggle", "strength", "misconception", "context"}


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def add_memory(db: Session, student_id: int, content: str, memory_type: str = "context",
               importance: float = 0.5) -> Memory | None:
    content = (content or "").strip()[:300]
    if len(content) < 6:
        return None
    memory_type = memory_type if memory_type in TYPES else "context"
    importance = max(0.0, min(1.0, float(importance)))
    vec = embed_one(content)
    existing = db.query(Memory).filter(Memory.student_id == student_id).all()
    existing = [m for m in existing if m.embedding and len(m.embedding) == len(vec)]
    if existing:
        sims = cosine_scores(vec, [m.embedding for m in existing])
        best = int(sims.argmax())
        dup = existing[best]
        if sims[best] >= 0.8 or _norm(dup.content) == _norm(content):
            dup.content = content  # newer wording wins
            dup.importance = max(dup.importance, importance)
            dup.updated_at = utcnow()
            dup.embedding = vec
            db.commit()
            return dup
    m = Memory(student_id=student_id, memory_type=memory_type, content=content,
               importance=importance, embedding=vec)
    db.add(m)
    db.commit()
    return m


def list_memories(db: Session, student_id: int) -> list[Memory]:
    return (db.query(Memory).filter(Memory.student_id == student_id)
            .order_by(Memory.importance.desc(), Memory.updated_at.desc()).all())


def delete_memory(db: Session, student_id: int, memory_id: int) -> bool:
    m = db.get(Memory, memory_id)
    if not m or m.student_id != student_id:
        return False
    db.delete(m)
    db.commit()
    return True
