from typing import Any, TypedDict


class TutorState(TypedDict, total=False):
    student_id: int
    conversation_id: int
    current_message: str
    conversation_history: list[dict]   # last few messages only
    session: dict                      # short-term memory (persisted per conversation)
    current_subject: str
    current_topic: str
    intent: str
    current_agent: str
    retrieved_memories: list[str]
    retrieved_documents: list[dict]
    student_answer: str
    assessment: dict
    mastery_information: list[dict]
    mastery_update: dict
    next_action: str
    payload: Any
    final_response: str
    trace: list[str]
