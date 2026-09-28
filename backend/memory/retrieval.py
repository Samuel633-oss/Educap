"""Relevance-based memory retrieval: similarity + importance + recency."""
from sqlalchemy.orm import Session

from models.tables import Memory, utcnow
from rag.embeddings import cosine_scores, embed_one


def retrieve_memories(db: Session, student_id: int, query: str, k: int = 4,
                      min_score: float = 0.2) -> list[str]:
    rows = db.query(Memory).filter(Memory.student_id == student_id).all()  # <- isolation
    if not rows or not query.strip():
        return []
    qvec = embed_one(query)
    rows = [m for m in rows if m.embedding and len(m.embedding) == len(qvec)]
    if not rows:
        return []
    sims = cosine_scores(qvec, [m.embedding for m in rows])
    now = utcnow()
    scored = []
    for m, sim in zip(rows, sims):
        age_days = max((now - m.updated_at).days, 0)
        recency = 1 / (1 + age_days / 14)
        # preferences/levels apply to almost any request, so they get a relevance floor
        floor = 0.25 if m.memory_type in ("preference", "level") else 0.0
        rel = max(float(sim), floor)
        score = 0.65 * rel + 0.25 * m.importance + 0.10 * recency
        if rel >= min_score:
            scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [f"[{m.memory_type}] {m.content}" for _, m in scored[:k]]
