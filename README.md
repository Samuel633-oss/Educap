# Educap — a small multi-agent AI tutor

One simple chat. Behind it, a **Supervisor** routes each message to a specialist agent, backed by
**memory**, **RAG** and a **mastery model**.

```
Student → Supervisor ─┬─ Tutor      Socratic   Exam   Assessment   Case
                      └─ Revision   Flashcards Planner Research
          ↑ memory retrieval + RAG retrieval + mastery snapshot (retrieved ONCE, passed down)
          ↓ post-process: Mastery Agent updates scores, memory extraction stores durable facts
```

## Run it
```bash
# 1. backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # put your OPENROUTER_API_KEY in .env
python -m pytest                # 16 tests, no API key needed (fake LLM)
uvicorn main:app --reload --port 8000

# 2. frontend (new terminal)
cd frontend
cp .env.local.example .env.local
npm install && npm run dev      # http://localhost:3000
```
Free OpenRouter models change and get rate-limited. Pick one at https://openrouter.ai/models?max_price=0
and set `EDUCAP_STRONG_MODEL` / `EDUCAP_FAST_MODEL`; `EDUCAP_FALLBACK_MODELS` are tried automatically.

## Layout
| Path | Responsibility |
|---|---|
| `backend/agents/` | one file per agent (`supervisor.py` decides who runs) |
| `backend/graph/` | LangGraph state + workflow (supervisor → context → agent → post) |
| `backend/memory/` | extraction (what to remember), storage (dedupe), retrieval (relevance) |
| `backend/rag/` | chunking, embeddings, ingestion, retrieval (always filtered by `student_id`) |
| `backend/tools/` | `search_knowledge, retrieve_memory, retrieve_rag_context, update_memory, update_mastery, calculator, web_search, flashcard_generator` |
| `backend/api/` | FastAPI routes + chat service (streams agent status to the UI) |
| `frontend/` | Next.js UI: chat, progress, memory, notes, history |
| `_legacy/` | the earlier Phase 1–2 scaffold, kept for reference (not used) |

See **LEARN.md** for a guided tour of every component.

## Known MVP limits
- **No real authentication.** A student is just an id kept in the browser. Isolation is enforced in every query
  by `student_id`, but add real auth (sessions/JWT) before public use.
- **Vectors are stored as JSON and compared in Python** (fine up to a few thousand chunks). The swap to
  `pgvector` is isolated in `rag/retrieval.py` and `memory/retrieval.py`; see LEARN.md.
- **Default embeddings are a local hashing model** (keyword-flavoured, free). For true semantic search set
  `EMBEDDING_PROVIDER=openai` with any OpenAI-compatible embeddings endpoint, then re-upload notes.
- Free LLMs are weaker at strict JSON; the code parses leniently, retries once, and falls back to plain text.
