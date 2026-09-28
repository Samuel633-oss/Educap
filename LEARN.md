# Learning guide: how Educap works

For each component: **What / Why / How / Connects to / Concept to learn.**

## 1. LLM abstraction — `backend/llm.py`
- **What:** one `chat()` interface; `OpenRouterProvider` implements it.
- **Why:** agents shouldn't know which vendor you use; free models fail often.
- **How:** tries the main model, then fallbacks on 429/5xx; strips `<think>` blocks; `ask_json` parses JSON leniently and retries once.
- **Connects:** every agent, the router and the memory extractor call `get_llm()`. Tests swap in a fake with `set_llm()`.
- **Learn:** the *provider abstraction* (dependency inversion), and why LLM output must be treated as untrusted text.

## 2. Supervisor — `agents/supervisor.py`
- **What:** decides the intent and topic of each message.
- **Why:** the student never picks an agent, but an LLM call per message is slow and costs tokens.
- **How:** (1) session rules (active case? pending quiz question → it's an *answer*), (2) regex patterns, (3) a cached fast-model call only if unsure or the topic changed.
- **Connects:** first node of the graph; its output decides which agent node runs.
- **Learn:** *cheap-first routing* (cascading classifiers). Most production routers are mostly rules.

## 3. LangGraph workflow — `graph/workflow.py`, `graph/state.py`
- **What:** a state machine: `supervisor → context → ONE agent → (assessment→exam chain) → post`.
- **Why:** explicit flow is debuggable; one shared `TutorState` carries only small things (no documents, no full history).
- **How:** nodes return partial state updates; a conditional edge picks the agent; the DB session is passed via `config`.
- **Learn:** graphs of nodes with shared state, conditional edges, streaming node updates ("Exam Agent is preparing a question…").

## 4. Context node — retrieve once, pass down
- **What:** fetches memories + notes chunks + mastery rows relevant to *this* message.
- **Why:** agents must not each search the database, and the LLM must not see your whole history.
- **How:** builds one query (topic + pending question + message), calls the retrieval tools, limits results (4 memories, 3 chunks, 6–15 mastery rows).
- **Learn:** *context engineering* — the biggest lever on quality and cost.

## 5. The agents
- **What:** each agent = one system prompt + the context it needs + a small `run(state)` function.
- **Why:** narrow prompts beat one giant "do everything" prompt, especially on small free models.
- **Highlights:**
  - *Exam* asks for JSON, adapts difficulty to the weakest concept, and stores the answer key **server-side** in the session.
  - *Assessment* grades MCQs in Python (reliable, free); the LLM only writes the explanation. Free text is graded as JSON.
  - *Socratic* escalates hints (level 1→4) and only reveals the answer at level 4.
  - *Case* keeps secret facts server-side and reveals them only when the student earns them.
  - *Revision* ranks concepts by `0.7·(1−mastery) + 0.3·staleness` (spaced-repetition idea) with no LLM.
  - *Flashcards, Planner, Research* are the extra agents (Research cites Wikipedia sources).
- **Learn:** prompt design per role, structured output, and keeping logic deterministic where an LLM isn't needed.

## 6. Mastery — `agents/mastery.py`
- **What:** per-concept score, attempts, correct/incorrect, last reviewed.
- **How:** exponential moving average `s' = s + α(target − s)`, `α = max(0.25, 1/(attempts+2))`.
- **Learn:** a *learner model* — the same family as Elo ratings / Bayesian knowledge tracing, simplified.

## 7. Memory — `memory/`
- **Short-term:** the conversation's `state` (topic, pending question, active quiz/case) is saved with the conversation.
- **Long-term:** durable facts like "prefers simple explanations". `extraction.py` runs a regex gate, then a fast LLM call; `storage.py` de-duplicates by similarity; `retrieval.py` scores `0.65·similarity + 0.25·importance + 0.10·recency`.
- **Learn:** memory ≠ history. Store *distilled facts*, retrieve by relevance.

## 8. RAG — `rag/`
- **Pipeline:** text/PDF → `chunk_text` (paragraph-aware, overlapping) → metadata → embeddings → DB → similarity search → keyword rerank → top-k.
- **Isolation:** `retrieve_chunks` filters `student_id` *in the SQL query*, before any scoring. Tests prove Bea can't see Alex's notes.
- **Learn:** embeddings, cosine similarity, chunking trade-offs, hybrid (semantic + keyword) reranking.
- **pgvector upgrade:** add a `vector(384)` column, then replace the Python cosine loop with
  `ORDER BY embedding <=> :q LIMIT k`, keeping the `WHERE student_id = :sid` filter.

## 9. Tools — `tools/builtin.py`
Small registered functions (`GET /api/tools` lists them). The **calculator** parses expressions with `ast` (never `eval`), and the Tutor uses it so arithmetic is exact. **Learn:** tools give LLM systems reliable abilities; keep them simple and safe.

## 10. Streaming API — `api/service.py`
`POST /api/chat/stream` sends newline-delimited JSON: a `status` event as soon as the Supervisor picks an agent, then a `final` event. **Learn:** streaming UX, NDJSON.

## Try these
1. `Teach me photosynthesis` → Tutor. 2. `Quiz me on it` → Exam (MCQ buttons). 3. Answer wrongly → Assessment + next question; watch **Progress**.
4. `I prefer simple explanations` → **Memory** tab. 5. Paste notes in **Notes**, then ask about them. 6. `Give me a clinical case about heart failure`. 7. `What should I revise?`
