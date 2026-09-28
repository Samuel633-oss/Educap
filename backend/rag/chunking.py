"""Chunking: split long text into overlapping, paragraph-aware pieces.

Why: embeddings work best on focused passages, and we only want to send the
few relevant passages to the LLM, never the whole document.
"""
import re


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    out, cur = [], ""
    for s in sentences:
        while len(s) > max_chars:  # pathological sentence: hard split
            out.append(s[:max_chars]); s = s[max_chars:]
        if len(cur) + len(s) + 1 > max_chars and cur:
            out.append(cur); cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_text(text: str, max_chars: int = 900, overlap: int = 120) -> list[str]:
    paragraphs = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n\s*\n", text or "")]
    pieces: list[str] = []
    for p in paragraphs:
        if not p:
            continue
        pieces.extend([p] if len(p) <= max_chars else _split_long(p, max_chars))
    chunks, cur = [], ""
    for piece in pieces:
        if cur and len(cur) + len(piece) + 2 > max_chars:
            chunks.append(cur)
            tail = cur[-overlap:]
            tail = tail[tail.find(" ") + 1:] if " " in tail else tail  # start on a word boundary
            cur = f"{tail}\n\n{piece}" if overlap else piece
        else:
            cur = f"{cur}\n\n{piece}".strip()
    if cur:
        chunks.append(cur)
    return chunks
