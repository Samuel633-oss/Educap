"""Research Agent: grounds an answer in web sources (Wikipedia by default) and cites them."""
from agents.base import chat, system_prompt
from tools.builtin import call_tool

ROLE = """ROLE=research. Answer using ONLY the sources below. Cite them as [1], [2]. If they do not cover the
question, say so plainly. Keep it under 250 words and end with one follow-up the student could explore."""


def run(state: dict) -> dict:
    query = state.get("current_topic") or state["current_message"]
    results = call_tool("web_search", query=query)
    if not results:
        return {"final_response": "I couldn't reach the web sources just now. I can still explain the topic from what I know - want that instead?"}
    sources = "\n\n".join(f"[{i}] {r['title']}: {r['extract'][:800]}" for i, r in enumerate(results, 1))
    reply = chat(system_prompt(ROLE), f"Sources:\n{sources}\n\nQuestion: {state['current_message']}", tier="strong", max_tokens=600)
    links = "\n".join(f"{i}. [{r['title']}]({r['url']})" for i, r in enumerate(results, 1))
    return {"final_response": f"{reply}\n\n**Sources**\n{links}"}
