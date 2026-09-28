"""Supervisor Agent: the orchestrator.

Routing strategy (cheap first):
  1. Rules for session-aware control flow (active case? pending quiz question?).
  2. Regex patterns for obvious intents - zero LLM cost.
  3. A fast-tier LLM call only when rules can't decide, or when the topic changed
     and we need to know its subject.
"""
import re

from llm import LLMError, get_llm

INTENTS = {"teach", "socratic", "quiz", "answer", "assess", "revise", "case",
           "flashcards", "plan", "research", "chat"}

PATTERNS = [
    ("revise", r"\b(what (should|do|to) (i )?(revise|review|study)|revision|revise|what to revise|review my weak)\b"),
    ("plan", r"\b(study plan|timetable|plan my (study|revision|week)|revision plan|schedule my)\b"),
    ("flashcards", r"\bflash ?cards?\b"),
    ("case", r"\b(clinical case|case study|patient case|scenario|simulat(e|ion)|give me a case|debugging challenge)\b"),
    ("assess", r"\b(test my understanding|assess me|how (well )?do i (know|understand)|check my (understanding|knowledge|level)|my progress|how am i doing)\b"),
    ("quiz", r"\b(quiz|test me|practice (question|problem)s?|ask me (some |a few )?(questions?|something)|give me (a |an |some )?(question|mcq|problem|practice)s?|mcqs?|next question|another (question|one))\b"),
    ("socratic", r"(don'?t (tell|give) me the answer|give me a hint|\bhints?\b|guide me|help me (think|figure)|let me (try|think))"),
    ("research", r"\b(search (the web|online|wikipedia)|look (it |this )?up|latest (news|research)|recent (news|research|developments))\b"),
    ("teach", r"\b(teach|explain|what (is|are|does)|how (does|do|is|are)|why|don'?t understand|do not understand|confused|walk me through|tell me about|help me understand|define|summari[sz]e|i'?m stuck)\b"),
]
STOP_QUIZ = r"\b(stop|end|finish|quit|enough)\b.*\b(quiz|questions?|test|practice)\b|^\s*(stop|quit)\s*[.!]?$"
END_CASE = r"\b(end|stop|quit|finish|exit)\b.*\b(case|scenario|simulation)\b|^\s*(stop|quit)\s*[.!]?$"
NEW_REQUEST = r"^\s*(explain|teach|tell me|what (is|are)|how (does|do)|why|can you|could you|i (don'?t|do not) understand|help me understand)\b"
CHITCHAT = r"^\s*(thanks|thank you|ok|okay|cool|great|got it|hi|hello|hey|nice|awesome)\b[\s.!]*$"

TOPIC_PATTERNS = [
    r"(?:teach me|explain|tell me about|walk me through|help me understand|define|summari[sz]e)\s+(?:about\s+|how\s+)?(?:the\s+)?(.+)",
    r"(?:quiz|test) me\s+(?:on|about)\s+(.+)",
    r"(?:questions?|problems?|mcqs?|practice)\s+(?:on|about|for)\s+(.+)",
    r"(?:case|scenario|simulation|case study)\s+(?:about|on|for|involving|of)\s+(.+)",
    r"flash ?cards?\s+(?:on|about|for)\s+(.+)",
    r"(?:i (?:don'?t|do not) understand|i'?m confused (?:about|by)|i'?m stuck (?:on|with)|struggling with)\s+(?:the\s+)?(.+)",
    r"what (?:is|are)\s+(?:a |an |the )?(.+)",
    r"how (?:does|do)\s+(?:a |an |the )?(.+?)\s+work",
]
PRONOUNS = {"it", "this", "that", "them", "those", "these", "more", "again", "something", "anything"}


def extract_topic(message: str) -> str | None:
    text = message.strip()
    for pat in TOPIC_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            topic = re.sub(r"\b(please|for me|to me|thanks)\b", "", m.group(1), flags=re.I)
            topic = re.sub(r"[?.!]+$", "", topic).strip(" ,")
            if topic and topic.lower() not in PRONOUNS and len(topic.split()) <= 10:
                return topic[:80]
    return None


def detect_intent(message: str, session: dict) -> tuple[str | None, str]:
    low = message.lower().strip()
    if session.get("active_case"):
        return "case", ("end" if re.search(END_CASE, low) else "")
    if session.get("pending_question"):
        if re.search(STOP_QUIZ, low):
            return "assess", "report_only"
        for intent in ("revise", "plan", "flashcards", "case", "assess", "quiz", "research"):
            if re.search(dict(PATTERNS)[intent], low):
                return intent, ""
        if re.search(dict(PATTERNS)["socratic"], low):
            return "socratic", ""
        if re.search(NEW_REQUEST, low):
            return "teach", ""
        return "answer", ""
    if re.search(STOP_QUIZ, low) and session.get("quiz", {}).get("active"):
        return "assess", "report_only"
    for intent, pat in PATTERNS:
        if re.search(pat, low):
            return intent, ""
    if re.match(CHITCHAT, low):
        return "chat", ""
    return None, ""


def _llm_classify(message: str, session: dict) -> dict:
    system = ("ROLE=router. Classify a student's message. Intents: teach (explain/learn something), "
              "socratic (wants hints/guidance, not the answer), quiz (wants practice questions), "
              "revise (what to review), plan (study schedule), case (scenario/case simulation), "
              "flashcards, research (look something up online), chat (small talk). "
              'Return JSON: {"intent":"...","subject":"broad school subject e.g. Biology","topic":"short topic or null"}')
    user = f"Current topic: {session.get('topic') or 'none'}\nMessage: {message[:400]}"
    try:
        data = get_llm().ask_json(system, user, tier="fast", cache=True)
    except LLMError:
        return {}
    return data if isinstance(data, dict) else {}


def _detect_subject(topic: str) -> str:
    try:
        data = get_llm().ask_json(
            "ROLE=router. Name the broad school subject (e.g. Biology, Mathematics, Medicine, Computer Science, "
            'History, Business, Languages) for this topic. Return JSON: {"subject":"..."}',
            f"Topic: {topic}", tier="fast", cache=True)
    except LLMError:
        return "General"
    subject = data.get("subject") if isinstance(data, dict) else None
    return str(subject)[:60] if subject else "General"


def classify(message: str, session: dict) -> dict:
    intent, flag = detect_intent(message, session)
    topic = None if (intent == "answer" or session.get("active_case")) else extract_topic(message)
    llm_info: dict = {}
    if intent is None or (topic is None and not session.get("topic") and intent in ("teach", "quiz", "flashcards", "socratic")):
        llm_info = _llm_classify(message, session)
        if intent is None:
            guess = llm_info.get("intent")
            intent = guess if guess in INTENTS else "teach"
        t = llm_info.get("topic")
        if topic is None and isinstance(t, str) and t.lower() not in ("null", "none", ""):
            topic = t[:80]
    prev_topic, subject = session.get("topic"), session.get("subject")
    if topic and (not prev_topic or topic.lower() != prev_topic.lower()):
        subject = llm_info.get("subject") or _detect_subject(topic)
    return {"intent": intent, "current_topic": topic or prev_topic, "current_subject": subject or "General",
            "next_action": flag}
