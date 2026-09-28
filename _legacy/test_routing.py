import pytest
from backend.agents.supervisor import parse_classification, heuristic_intent
from backend.graph.workflow import build_graph

class FakeLLM:
    """Returns a canned classification for routing calls, echo for agent calls."""
    def __init__(self, intent): self.intent = intent
    async def chat(self, messages, *, fast=False, **kw):
        return f'{{"intent": "{self.intent}", "subject": "Biology", "topic": "Photosynthesis"}}' if fast else "agent reply"

@pytest.mark.parametrize("intent,agent", [("teach","tutor"),("hint","socratic"),("quiz","exam"),("answer_quiz","exam"),("other","tutor")])
@pytest.mark.asyncio
async def test_routing(intent, agent):
    out = await build_graph(FakeLLM(intent)).ainvoke({"current_message": "x", "conversation_history": []})
    assert out["current_agent"] == agent and out["final_response"] == "agent reply"
    assert out["current_topic"] == "Photosynthesis"

def test_bad_json_falls_back():
    assert parse_classification("sure! here you go") is None
    assert parse_classification('blah {"intent": "nonsense"}') is None
    assert heuristic_intent("quiz me on anatomy", None) == "quiz"
    assert heuristic_intent("Don't tell me the answer", None) == "hint"
    assert heuristic_intent("mitochondria", "exam") == "answer_quiz"
    assert heuristic_intent("explain derivatives", None) == "teach"


# --- API + isolation ---
from fastapi.testclient import TestClient
from backend.main import app
import backend.api.chat as chat_api

def test_api_and_isolation(monkeypatch):
    monkeypatch.setattr(chat_api, "_graph", build_graph(FakeLLM("quiz")))
    c = TestClient(app)
    r = c.post("/api/chat", json={"student_id": "student-aaaa", "message": "quiz me"})
    assert r.status_code == 200 and r.json()["agent"] == "exam"
    conv = r.json()["conversation_id"]
    # another student must not be able to use this conversation
    r2 = c.post("/api/chat", json={"student_id": "student-bbbb", "message": "hi", "conversation_id": conv})
    assert r2.status_code == 403
