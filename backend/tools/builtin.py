"""Tools: small, well-named functions agents/graph nodes can call.

Each tool is registered in TOOLS so they are discoverable (GET /api/tools) and
easy to extend. Keep tools boring: input -> output, no hidden state.
"""
import ast
import math
import operator as op
import re
from dataclasses import dataclass
from typing import Callable

import httpx
from sqlalchemy.orm import Session

from agents import mastery as mastery_agent
from llm import LLMError, get_llm
from memory.retrieval import retrieve_memories
from memory.storage import add_memory
from rag.retrieval import retrieve_chunks


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable


TOOLS: dict[str, Tool] = {}


def tool(name: str, description: str):
    def deco(fn):
        TOOLS[name] = Tool(name, description, fn)
        return fn
    return deco


def call_tool(name: str, **kwargs):
    return TOOLS[name].fn(**kwargs)


@tool("retrieve_memory", "Relevant long-term facts about the student for a query.")
def retrieve_memory(db: Session, student_id: int, query: str, k: int = 4) -> list[str]:
    return retrieve_memories(db, student_id, query, k=k)


@tool("retrieve_rag_context", "Relevant chunks of the student's own study material.")
def retrieve_rag_context(db: Session, student_id: int, query: str, subject: str | None = None, k: int = 3):
    return retrieve_chunks(db, student_id, query, subject=subject, k=k)


@tool("update_memory", "Store a durable learning fact about the student.")
def update_memory(db: Session, student_id: int, content: str, memory_type: str = "context", importance: float = 0.5):
    return add_memory(db, student_id, content, memory_type, importance)


@tool("update_mastery", "Record a right/wrong attempt on a concept and update the mastery score.")
def update_mastery(db: Session, student_id: int, subject: str, topic: str, concept: str,
                   correct: bool, score: float | None = None):
    return mastery_agent.record_attempt(db, student_id, subject, topic, concept, correct, score)


@tool("search_knowledge", "Search the student's material first; optionally fall back to the web.")
def search_knowledge(db: Session, student_id: int, query: str, subject: str | None = None,
                     allow_web: bool = False) -> dict:
    docs = retrieve_chunks(db, student_id, query, subject=subject, k=3)
    web = web_search(query) if (allow_web and not docs) else []
    return {"documents": docs, "web": web}


# ---- safe calculator -------------------------------------------------------
_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
        ast.Pow: op.pow, ast.Mod: op.mod, ast.USub: op.neg, ast.UAdd: op.pos, ast.FloorDiv: op.floordiv}
_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log,
          "ln": math.log, "log10": math.log10, "exp": math.exp, "abs": abs}
_CONST = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        if isinstance(node.op, ast.Pow) and abs(_eval(node.right)) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONST:
        return _CONST[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("unsupported expression")


@tool("calculator", "Evaluate an arithmetic expression exactly (no eval()).")
def calculator(expression: str) -> str | None:
    try:
        expr = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
        val = _eval(ast.parse(expr.strip(), mode="eval").body)
        return f"{val:.10g}" if isinstance(val, float) else str(val)
    except Exception:
        return None


MATH_RE = re.compile(r"(?<![\w.])(\d[\d\s.,]*\s*[-+*/^×÷%]\s*[\d(][\d\s.,+\-*/^()×÷]*)")


def find_arithmetic(message: str) -> str | None:
    m = MATH_RE.search(message or "")
    return m.group(1).strip().rstrip("?.,") if m else None


@tool("web_search", "Look up a topic on Wikipedia (free, no API key). Returns titles, extracts, URLs.")
def web_search(query: str, limit: int = 3) -> list[dict]:
    try:
        r = httpx.get("https://en.wikipedia.org/w/api.php", timeout=15, headers={"User-Agent": "Educap/1.0"},
                      params={"action": "query", "format": "json", "generator": "search", "gsrsearch": query,
                              "gsrlimit": limit, "prop": "extracts", "exintro": 1, "explaintext": 1,
                              "exchars": 1000})
        pages = (r.json().get("query") or {}).get("pages", {})
        ordered = sorted(pages.values(), key=lambda p: p.get("index", 99))
        return [{"title": p["title"], "extract": p.get("extract", ""),
                 "url": f"https://en.wikipedia.org/?curid={p['pageid']}"} for p in ordered]
    except Exception:
        return []


@tool("flashcard_generator", "Make question/answer flashcards from a topic and optional study notes.")
def flashcard_generator(topic: str, context: str = "", n: int = 6) -> list[dict]:
    system = (f"ROLE=flashcards. Create {n} concise study flashcards. "
              'Return JSON: {"cards":[{"front":"question or term","back":"short answer"}]}')
    user = f"Topic: {topic}\n" + (f"Base them on these notes:\n{context[:2500]}" if context else "")
    try:
        data = get_llm().ask_json(system, user, tier="strong", max_tokens=900)
    except LLMError:
        return []
    cards = (data or {}).get("cards", []) if isinstance(data, dict) else (data or [])
    return [{"front": str(c["front"]), "back": str(c["back"])} for c in cards
            if isinstance(c, dict) and "front" in c and "back" in c][:n]
