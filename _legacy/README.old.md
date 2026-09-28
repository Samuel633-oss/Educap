# Educap
A multi-agent AI tutor. One chat; a supervisor routes each message to the right agent.

## Run
```bash
cp .env.example .env            # add OPENROUTER_API_KEY
pip install -r requirements.txt
python -m pytest                # 7 tests, no API key needed
uvicorn backend.main:app --reload --port 8000

cd frontend && cp .env.local.example .env.local && npm install && npm run dev
```
Open http://localhost:3000

## Status
Phase 1-2 done: Supervisor, Tutor, Socratic, Exam (LangGraph). Next: Assessment -> Memory -> RAG -> Mastery/Revision -> Case.
