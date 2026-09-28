"""LangGraph workflow: supervisor -> context -> ONE specialist -> (chain?) -> post-process.

Nodes are tiny wrappers; the intelligence lives in the agents. The DB session is passed
through config["configurable"]["db"] so the compiled graph can be reused across requests.
"""
from langgraph.graph import END, START, StateGraph

from agents import (assessment, case, exam, flashcards, planner, research, revision,
                    socratic, supervisor, tutor)
from agents import mastery as mastery_agent
from graph.state import TutorState
from memory.extraction import extract_and_store
from memory.storage import add_memory
from tools.builtin import call_tool

INTENT_TO_AGENT = {"teach": "tutor", "chat": "tutor", "socratic": "socratic", "quiz": "exam",
                   "answer": "assessment", "assess": "assessment", "revise": "revision", "case": "case",
                   "flashcards": "flashcards", "plan": "planner", "research": "research"}
AGENTS = {"tutor": tutor, "socratic": socratic, "exam": exam, "assessment": assessment, "case": case,
          "revision": revision, "flashcards": flashcards, "planner": planner, "research": research}
NO_RAG = {"revise", "plan", "research", "assess"}
WIDE_MASTERY = {"revise", "plan", "assess"}


def supervisor_node(state: TutorState, config) -> dict:
    session = dict(state.get("session") or {})
    info = supervisor.classify(state["current_message"], session)
    if info["current_topic"] != session.get("topic") and session.get("topic"):
        session.update(quiz=None, pending_question=None, hint_level=0)  # topic switch = fresh practice round
    session.update(topic=info["current_topic"], subject=info["current_subject"], last_intent=info["intent"])
    return {**info, "session": session, "trace": [f"supervisor -> {info['intent']}"]}


def context_node(state: TutorState, config) -> dict:
    """Retrieve ONLY what this task needs (memory + RAG + mastery) once, for all agents."""
    db, sid, intent = config["configurable"]["db"], state["student_id"], state["intent"]
    pending = (state["session"].get("pending_question") or {}).get("question", "")
    query = f"{state.get('current_topic') or ''} {pending} {state['current_message']}".strip()
    memories = call_tool("retrieve_memory", db=db, student_id=sid, query=query, k=4)
    docs = [] if intent in NO_RAG else call_tool("retrieve_rag_context", db=db, student_id=sid, query=query,
                                                  subject=state.get("current_subject"), k=3)
    topic = None if intent in WIDE_MASTERY else state.get("current_topic")
    rows = mastery_agent.snapshot(db, sid, topic=topic, limit=15 if intent in WIDE_MASTERY else 6)
    return {"retrieved_memories": memories, "retrieved_documents": docs, "mastery_information": rows,
            "trace": state["trace"] + [f"context: {len(memories)} memories, {len(docs)} chunks, {len(rows)} mastery rows"]}


def make_node(name: str):
    def node(state: TutorState, config) -> dict:
        out = AGENTS[name].run(state)
        out["current_agent"] = name
        out["trace"] = state["trace"] + [f"{name} agent"]
        return out
    return node


def route(state: TutorState) -> str:
    return INTENT_TO_AGENT.get(state["intent"], "tutor")


def after_assessment(state: TutorState) -> str:
    return "exam" if state.get("next_action") == "exam_next" else "post"


def post_node(state: TutorState, config) -> dict:
    """Mastery Agent + memory extraction. Runs after the specialist has answered."""
    db, sid = config["configurable"]["db"], state["student_id"]
    out: dict = {}
    a = state.get("assessment")
    if a and a.get("score") is not None and a.get("concept"):
        upd = call_tool("update_mastery", db=db, student_id=sid, subject=state.get("current_subject") or "General",
                        topic=state.get("current_topic") or a["concept"], concept=a["concept"],
                        correct=bool(a["correct"]), score=a["score"])
        out["mastery_update"] = upd
        if a.get("misconception"):
            call_tool("update_memory", db=db, student_id=sid, memory_type="misconception", importance=0.7,
                      content=f"Misconception about {a['concept']}: {a['misconception']}"[:280])
        if upd["attempts"] >= 3 and upd["after"] < 0.5:
            call_tool("update_memory", db=db, student_id=sid, memory_type="struggle", importance=0.8,
                      content=f"Repeatedly struggles with {a['concept']}")
        if a.get("confidence") == "low" and a["correct"]:
            call_tool("update_memory", db=db, student_id=sid, memory_type="context", importance=0.4,
                      content=f"Answered {a['concept']} correctly but with low confidence")
    if state["intent"] not in ("answer", "case"):
        extract_and_store(db, sid, state["current_message"], state.get("current_topic"))
    out["trace"] = state["trace"] + ["post: mastery + memory"]
    return out


def build_graph():
    g = StateGraph(TutorState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("context", context_node)
    g.add_node("post", post_node)
    for name in AGENTS:
        g.add_node(name, make_node(name))
    g.add_edge(START, "supervisor")
    g.add_edge("supervisor", "context")
    g.add_conditional_edges("context", route, {n: n for n in AGENTS})
    for name in AGENTS:
        if name != "assessment":
            g.add_edge(name, "post")
    g.add_conditional_edges("assessment", after_assessment, {"exam": "exam", "post": "post"})
    g.add_edge("post", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
