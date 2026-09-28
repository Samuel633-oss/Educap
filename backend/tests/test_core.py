from agents import mastery
from agents.supervisor import classify, detect_intent, extract_topic
from api.service import chat_once
from memory.extraction import extract_and_store, should_extract
from memory.retrieval import retrieve_memories
from memory.storage import add_memory
from models.tables import Message
from rag.chunking import chunk_text
from rag.ingestion import ingest_text
from rag.retrieval import retrieve_chunks
from tools.builtin import calculator, find_arithmetic


# ---- supervisor routing -------------------------------------------------
def test_routing_rules():
    cases = {"Teach me photosynthesis.": "teach", "Explain derivatives.": "teach", "Quiz me on anatomy.": "quiz",
             "I don't understand recursion.": "teach", "Give me a clinical case about heart failure.": "case",
             "What should I revise?": "revise", "Don't tell me the answer. Give me a hint.": "socratic",
             "Test my understanding.": "assess", "Make flashcards on the Krebs cycle": "flashcards",
             "Ask me questions about it.": "quiz", "Make me a study plan": "plan"}
    for msg, want in cases.items():
        assert detect_intent(msg, {})[0] == want, msg


def test_routing_is_session_aware():
    pending = {"pending_question": {"question": "q"}}
    assert detect_intent("B", pending)[0] == "answer"
    assert detect_intent("give me a hint", pending)[0] == "socratic"
    assert detect_intent("explain the Calvin cycle", pending)[0] == "teach"
    assert detect_intent("anything", {"active_case": {"turn": 1}})[0] == "case"


def test_topic_extraction():
    assert extract_topic("Teach me photosynthesis.") == "photosynthesis"
    assert extract_topic("Quiz me on anatomy") == "anatomy"
    assert extract_topic("Ask me questions about it") is None


def test_classify_uses_llm_only_when_needed(llm):
    info = classify("Quiz me on anatomy", {})
    assert info["intent"] == "quiz" and info["current_topic"] == "anatomy" and info["current_subject"] == "Biology"
    assert llm.calls == ["router"]  # only the subject lookup, no intent call


# ---- mastery --------------------------------------------------------------
def test_mastery_updates(db, alex):
    r = mastery.record_attempt(db, alex.id, "Biology", "Photosynthesis", "Calvin cycle", True)
    assert r["after"] > r["before"]
    r2 = mastery.record_attempt(db, alex.id, "Biology", "Photosynthesis", "calvin cycle", False)
    assert r2["after"] < r["after"] and r2["attempts"] == 2  # case-insensitive same row
    assert len(mastery.snapshot(db, alex.id)) == 1


# ---- memory ----------------------------------------------------------------
def test_memory_extraction_and_retrieval(db, alex, llm):
    assert should_extract("I prefer simple explanations") and not should_extract("Explain derivatives")
    assert extract_and_store(db, alex.id, "I prefer simple explanations with examples", "calculus")
    assert not extract_and_store(db, alex.id, "Explain derivatives", "calculus")
    got = retrieve_memories(db, alex.id, "explain integration simply")
    assert any("simple explanations" in g for g in got)


def test_memory_dedupe_and_isolation(db, alex, bea):
    add_memory(db, alex.id, "Struggles with integration by parts", "struggle", 0.6)
    add_memory(db, alex.id, "Struggles with integration by parts.", "struggle", 0.9)
    assert len(retrieve_memories(db, alex.id, "integration by parts")) == 1
    assert retrieve_memories(db, bea.id, "integration by parts") == []


# ---- RAG ---------------------------------------------------------------------
NOTES = ("The Calvin cycle takes place in the stroma and uses ATP and NADPH to fix carbon dioxide into sugar.\n\n"
         "Light reactions occur in the thylakoid membrane where chlorophyll absorbs light energy.\n\n") * 3


def test_chunking_and_retrieval(db, alex):
    assert all(len(c) < 1100 for c in chunk_text("word " * 1000))
    ingest_text(db, alex.id, "Bio notes", NOTES + "Mitochondria produce ATP through the electron transport chain.\n\n" * 2, "Biology")
    hits = retrieve_chunks(db, alex.id, "where does the Calvin cycle happen")
    assert hits and "Calvin" in hits[0]["content"] and hits[0]["title"] == "Bio notes"


def test_rag_isolation(db, alex, bea):
    ingest_text(db, alex.id, "Private", NOTES, "Biology")
    assert retrieve_chunks(db, alex.id, "Calvin cycle stroma")
    assert retrieve_chunks(db, bea.id, "Calvin cycle stroma") == []


# ---- tools ---------------------------------------------------------------------
def test_calculator_is_safe():
    assert calculator("2^10 + 3*4") == "1036"
    assert calculator("__import__('os').system('ls')") is None
    assert find_arithmetic("what is 12*7?") == "12*7"


# ---- full graph: teach -> quiz -> answer -> mastery ----------------------------
def test_full_learning_loop(db, alex, llm):
    r1 = chat_once(db, alex.id, "Teach me photosynthesis")
    assert r1["agent"] == "tutor" and "Photosynthesis" in r1["reply"]
    cid = r1["conversation_id"]
    r2 = chat_once(db, alex.id, "Quiz me on photosynthesis", cid)
    assert r2["agent"] == "exam" and "Thylakoid" in r2["reply"] and r2["payload"]["options"]
    r3 = chat_once(db, alex.id, "A", cid)  # wrong (key is B)
    assert r3["agent"] == "exam" and "Not quite" in r3["reply"] and "Question 2" in r3["reply"]  # assessment -> exam chain
    assert r3["payload"]["mastery_update"]["after"] < 0.5
    rows = mastery.snapshot(db, alex.id)
    assert rows[0]["concept"] == "Light reactions" and rows[0]["incorrect_answers"] == 1
    r4 = chat_once(db, alex.id, "What should I revise?", cid)
    assert r4["agent"] == "revision"
    assert db.query(Message).filter_by(conversation_id=cid).count() == 8


def test_case_flow_and_completion(db, alex, llm):
    from tests.conftest import FakeLLM
    r = chat_once(db, alex.id, "Give me a clinical case about heart failure")
    assert r["agent"] == "case" and "not real medical advice" in r["reply"]
    assert "###HIDDEN###" not in r["reply"] and "Diagnosis: heart failure" not in r["reply"]  # secrets stay server-side
    cid = r["conversation_id"]
    r2 = chat_once(db, alex.id, "What is the blood pressure?", cid)
    assert r2["agent"] == "case" and "BP" in r2["reply"]
    # completion marker -> case closes and reasoning is scored into mastery
    orig = FakeLLM.chat
    FakeLLM.chat = lambda self, m, **k: ('Well reasoned. Answer: HFrEF.\n[[CASE_COMPLETE score=0.8 concept="Heart failure reasoning"]]'
                                         if "ROLE=case_continue" in m[0]["content"] else orig(self, m, **k))
    try:
        r3 = chat_once(db, alex.id, "My final diagnosis is heart failure", cid)
    finally:
        FakeLLM.chat = orig
    assert "Case complete" in r3["reply"] and "CASE_COMPLETE" not in r3["reply"]
    assert mastery.snapshot(db, alex.id)[0]["concept"] == "Heart failure reasoning"
    assert chat_once(db, alex.id, "Explain the heart", cid)["agent"] == "tutor"  # case no longer active


def test_assess_starts_diagnostic_and_stop_reports(db, alex, llm):
    mastery.record_attempt(db, alex.id, "Biology", "Photosynthesis", "Calvin cycle", False)
    r = chat_once(db, alex.id, "Test my understanding of photosynthesis")
    assert "Needs improvement" in r["reply"] and "Question 1" in r["reply"]  # assessment -> exam chain
    cid = r["conversation_id"]
    r2 = chat_once(db, alex.id, "stop the quiz", cid)
    assert r2["agent"] == "assessment" and "Question" not in r2["reply"]
    assert chat_once(db, alex.id, "hello", cid)["agent"] == "tutor"


def test_socratic_hides_answer(db, alex, llm):
    cid = chat_once(db, alex.id, "Quiz me on photosynthesis")["conversation_id"]
    r = chat_once(db, alex.id, "give me a hint", cid)
    assert r["agent"] == "socratic"
