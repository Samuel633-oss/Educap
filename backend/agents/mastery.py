"""Mastery Agent: a deterministic learner model (no LLM = free and predictable).

score' = score + alpha * (target - score), alpha = max(0.25, 1/(attempts+2))
This is an exponential moving average: early attempts move the score a lot, later
ones less, but recent performance always matters.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.tables import Mastery, utcnow

WEAK, STRONG = 0.6, 0.8


def record_attempt(db: Session, student_id: int, subject: str, topic: str, concept: str,
                   correct: bool, score: float | None = None) -> dict:
    subject, topic, concept = (subject or "General").strip()[:120], (topic or concept).strip()[:120], concept.strip()[:160]
    row = (db.query(Mastery).filter(
        Mastery.student_id == student_id, func.lower(Mastery.subject) == subject.lower(),
        func.lower(Mastery.topic) == topic.lower(), func.lower(Mastery.concept) == concept.lower()).first())
    if not row:
        row = Mastery(student_id=student_id, subject=subject, topic=topic, concept=concept,
                      mastery_score=0.5, confidence=0.0, attempts=0, correct_answers=0, incorrect_answers=0)
        db.add(row)
    target = score if score is not None else (1.0 if correct else 0.0)
    before = row.mastery_score
    alpha = max(0.25, 1 / (row.attempts + 2))
    row.mastery_score = round(max(0.0, min(1.0, before + alpha * (target - before))), 3)
    row.attempts += 1
    row.correct_answers += 1 if correct else 0
    row.incorrect_answers += 0 if correct else 1
    row.confidence = round(min(1.0, row.attempts / 6), 2)  # how much evidence we have
    row.last_reviewed = utcnow()
    db.commit()
    return {"concept": concept, "topic": topic, "before": round(before, 2), "after": row.mastery_score,
            "attempts": row.attempts}


def _to_dict(r: Mastery) -> dict:
    return {"id": r.id, "subject": r.subject, "topic": r.topic, "concept": r.concept,
            "mastery_score": r.mastery_score, "confidence": r.confidence, "attempts": r.attempts,
            "correct_answers": r.correct_answers, "incorrect_answers": r.incorrect_answers,
            "last_reviewed": r.last_reviewed.isoformat() if r.last_reviewed else None}


def snapshot(db: Session, student_id: int, topic: str | None = None, limit: int = 8) -> list[dict]:
    q = db.query(Mastery).filter(Mastery.student_id == student_id)
    if topic:
        scoped = q.filter(func.lower(Mastery.topic) == topic.lower()).order_by(Mastery.mastery_score).limit(limit).all()
        if scoped:
            return [_to_dict(r) for r in scoped]
    return [_to_dict(r) for r in q.order_by(Mastery.mastery_score).limit(limit).all()]


def strengths_and_weaknesses(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    return ([r for r in rows if r["mastery_score"] >= STRONG],
            [r for r in rows if r["mastery_score"] < WEAK])
