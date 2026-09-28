"""Embeddings: turn text into vectors so 'similar meaning' becomes 'close in space'.

Default = HashingEmbedder: free, local, deterministic (keyword-overlap flavoured).
For true semantic search set EMBEDDING_PROVIDER=openai and point to any
OpenAI-compatible /embeddings endpoint. (Re-ingest documents if you switch.)
"""
import hashlib
import re
from abc import ABC, abstractmethod

import httpx
import numpy as np

from config import settings

STOP = set("a an the and or of to in on for with is are was were be been it this that these those "
           "as at by from what how why do does did can could you i me my we our your not no yes "
           "explain teach tell about please give".split())


def stem(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("ies"): return tok[:-3] + "y"
    if len(tok) > 5 and tok.endswith("ing"): return tok[:-3]
    if len(tok) > 4 and tok.endswith("es"): return tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"): return tok[:-1]
    return tok


def tokens(text: str) -> list[str]:
    return [stem(t) for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in STOP]


class Embedder(ABC):
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder(Embedder):
    def __init__(self, dim: int = 384):
        self.dim = dim

    def _one(self, text: str) -> list[float]:
        toks = tokens(text)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]  # unigrams + bigrams
        v = np.zeros(self.dim)
        for f in feats:
            h = hashlib.md5(f.encode()).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            v[idx] += 1.0 if h[4] % 2 else -1.0
        v = np.sign(v) * np.sqrt(np.abs(v))  # sublinear term frequency
        n = np.linalg.norm(v)
        return (v / n).tolist() if n else v.tolist()

    def embed(self, texts):
        return [self._one(t) for t in texts]


class OpenAICompatEmbedder(Embedder):
    dim = 0

    def embed(self, texts):
        r = httpx.post(f"{settings.embedding_base_url}/embeddings",
                       headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                       json={"model": settings.embedding_model, "input": texts}, timeout=60)
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = OpenAICompatEmbedder() if settings.embedding_provider == "openai" else HashingEmbedder()
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_embedder().embed(texts)


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine_scores(query: list[float], matrix: list[list[float]]) -> np.ndarray:
    q = np.asarray(query, dtype=float)
    m = np.asarray(matrix, dtype=float)
    denom = (np.linalg.norm(m, axis=1) * (np.linalg.norm(q) or 1.0)) + 1e-9
    return (m @ q) / denom
