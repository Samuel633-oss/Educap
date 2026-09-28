import os, sys, tempfile, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["OPENROUTER_API_KEY"] = "test"

import pytest
from database.db import SessionLocal, init_db, Base, engine
from llm import LLMProvider, set_llm
from models.tables import Student


class FakeLLM(LLMProvider):
    """Deterministic stand-in: answers based on the ROLE=... tag in the system prompt."""
    def __init__(self): self.calls = []

    def chat(self, messages, tier="strong", temperature=0.5, max_tokens=900):
        system = messages[0]["content"]
        role = re.search(r"ROLE=(\w+)", system).group(1)
        self.calls.append(role)
        if role == "router":
            if "broad school subject" in system:
                return '{"subject":"Medicine"}' if "heart" in messages[1]["content"].lower() else '{"subject":"Biology"}'
            return '{"intent":"teach","subject":"Biology","topic":"photosynthesis"}'
        if role == "tutor": return "Photosynthesis turns light into chemical energy."
        if role == "socratic": return "What is the first thing the plants need?"
        if role == "exam_generate":
            return json.dumps({"question": "Where do the light reactions occur?", "type": "mcq",
                               "options": ["A. Stroma", "B. Thylakoid membrane", "C. Nucleus", "D. Ribosome"],
                               "answer": "B", "concept": "Light reactions", "explanation": "Thylakoids hold chlorophyll."})
        if role == "assessment_feedback": return "The thylakoid membrane holds the photosystems."
        if role == "assessment_grade": return '{"correct": false, "score": 0.2, "concept": "Calvin cycle", "misconception": "Thinks it needs light directly", "feedback": "Close, but no."}'
        if role == "memory_extractor":
            return '{"facts":[{"content":"Student prefers simple explanations with examples","type":"preference","importance":0.8}]}'
        if role == "revision": return "1. Review the Calvin cycle."
        if role == "flashcards": return '{"cards":[{"front":"What is ATP?","back":"Energy currency"}]}'
        if role == "case_start": return "A 60-year-old presents with breathlessness.\n###HIDDEN###\nDiagnosis: heart failure."
        if role == "case_continue": return "BP is 100/60. What next?"
        if role == "planner": return "Day 1: review."
        return "ok"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine); init_db()
    yield


@pytest.fixture
def llm():
    f = FakeLLM(); set_llm(f); yield f; set_llm(None)


@pytest.fixture
def db():
    s = SessionLocal(); yield s; s.close()


@pytest.fixture
def alex(db):
    s = Student(name="Alex"); db.add(s); db.commit(); return s


@pytest.fixture
def bea(db):
    s = Student(name="Bea"); db.add(s); db.commit(); return s
