"""Ingestion: source -> text -> chunks -> metadata -> embeddings -> database."""
import io
from datetime import datetime

from sqlalchemy.orm import Session

from models.tables import Document, DocumentChunk, utcnow
from rag.chunking import chunk_text
from rag.embeddings import embed_texts


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    return data.decode("utf-8", errors="ignore")


def ingest_text(db: Session, student_id: int, title: str, text: str, subject: str = "General",
                topic: str = "", source: str = "pasted text") -> Document:
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No readable text found in this material.")
    doc = Document(student_id=student_id, title=title[:200], subject=subject or "General",
                   source=source, chunk_count=len(chunks))
    db.add(doc)
    db.flush()
    vectors = embed_texts(chunks)
    now = utcnow()
    for i, (content, vec) in enumerate(zip(chunks, vectors)):
        db.add(DocumentChunk(
            document_id=doc.id, student_id=student_id, content=content, embedding=vec,
            meta={"document_id": doc.id, "student_id": student_id, "subject": doc.subject,
                  "topic": topic, "source": source, "chunk_id": f"{doc.id}-{i}",
                  "created_at": now.isoformat()}))
    db.commit()
    return doc


def delete_document(db: Session, student_id: int, document_id: int) -> bool:
    doc = db.get(Document, document_id)
    if not doc or doc.student_id != student_id:  # isolation check
        return False
    db.query(DocumentChunk).filter_by(document_id=document_id, student_id=student_id).delete()
    db.delete(doc)
    db.commit()
    return True
