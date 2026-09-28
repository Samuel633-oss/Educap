"""Retrieval: similarity search + keyword rerank, ALWAYS filtered by student_id in SQL."""
from sqlalchemy.orm import Session

from models.tables import Document, DocumentChunk
from rag.embeddings import cosine_scores, embed_one, tokens


def retrieve_chunks(db: Session, student_id: int, query: str, subject: str | None = None,
                    k: int = 4, min_score: float = 0.15) -> list[dict]:
    rows = (db.query(DocumentChunk).filter(DocumentChunk.student_id == student_id)  # <- isolation
            .limit(5000).all())
    if not rows or not query.strip():
        return []
    qvec = embed_one(query)
    rows = [r for r in rows if r.embedding and len(r.embedding) == len(qvec)]
    if not rows:
        return []
    sims = cosine_scores(qvec, [r.embedding for r in rows])
    qtok = set(tokens(query))
    titles = {d.id: d.title for d in db.query(Document).filter(
        Document.id.in_({r.document_id for r in rows})).all()}
    scored = []
    for r, sim in zip(rows, sims):
        overlap = len(qtok & set(tokens(r.content))) / len(qtok) if qtok else 0.0
        score = 0.7 * float(sim) + 0.3 * overlap  # rerank: semantic + keyword
        if subject and (r.meta or {}).get("subject", "").lower() == subject.lower():
            score += 0.03
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"content": r.content, "title": titles.get(r.document_id, "Notes"),
             "document_id": r.document_id, "chunk_id": (r.meta or {}).get("chunk_id"),
             "score": round(s, 3)} for s, r in scored[:k] if s >= min_score]
