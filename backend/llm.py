"""LLM abstraction.

Agents never talk to a provider directly - they call get_llm().chat(...).
To switch providers, write another LLMProvider subclass and change get_llm().
"""
import hashlib
import json
import re
import time
from abc import ABC, abstractmethod

import httpx

from config import settings


class LLMError(Exception):
    pass


def clean_output(text: str) -> str:
    """Strip <think> blocks that some reasoning models emit."""
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def extract_json(text: str):
    """Find the first balanced JSON object/array in free-form model output."""
    text = clean_output(text)
    text = re.sub(r"```(?:json)?", "", text)
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break
            start = text.find(opener, start + 1)
    return None


class LLMProvider(ABC):
    _cache: dict[str, str] = {}

    @abstractmethod
    def chat(self, messages: list[dict], tier: str = "strong",
             temperature: float = 0.5, max_tokens: int = 900) -> str: ...

    def ask(self, system: str, user: str, tier: str = "strong", cache: bool = False, **kw) -> str:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if not cache:
            return self.chat(msgs, tier=tier, **kw)
        key = hashlib.sha1(f"{tier}|{system}|{user}".encode()).hexdigest()
        if key not in self._cache:
            if len(self._cache) > 500:
                self._cache.clear()
            self._cache[key] = self.chat(msgs, tier=tier, **kw)
        return self._cache[key]

    def ask_json(self, system: str, user: str, tier: str = "fast", cache: bool = False,
                 retries: int = 1, **kw):
        """Ask for JSON. Free models often wrap/garble it, so parse leniently and retry once."""
        nudge = "\n\nReply with valid JSON only. No commentary."
        for attempt in range(retries + 1):
            raw = self.ask(system + nudge, user, tier=tier, cache=cache and attempt == 0,
                           temperature=0.2 if attempt else kw.pop("temperature", 0.3), **kw)
            data = extract_json(raw)
            if data is not None:
                return data
        return None


class OpenRouterProvider(LLMProvider):
    def chat(self, messages, tier="strong", temperature=0.5, max_tokens=900) -> str:
        if not settings.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY is not set. Add it to backend/.env")
        primary = settings.fast_model if tier == "fast" else settings.strong_model
        models = [primary] + [m for m in settings.fallback_models if m != primary]
        last_error = "unknown error"
        for model in models:
            msgs = self._prepare(messages, model)
            for attempt in range(2):
                try:
                    r = httpx.post(
                        f"{settings.openrouter_base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {settings.openrouter_api_key}",
                                 "X-Title": "Educap"},
                        json={"model": model, "messages": msgs,
                              "temperature": temperature, "max_tokens": max_tokens},
                        timeout=90)
                    if r.status_code in (408, 429, 500, 502, 503):
                        last_error = f"{model}: HTTP {r.status_code}"
                        time.sleep(1.2 * (attempt + 1))
                        continue
                    r.raise_for_status()
                    content = clean_output(r.json()["choices"][0]["message"]["content"] or "")
                    if content:
                        return content
                    last_error = f"{model}: empty response"
                    break
                except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                    last_error = f"{model}: {e}"
                    break
        raise LLMError(f"All models failed ({last_error})")

    @staticmethod
    def _prepare(messages, model):
        """Some free models (e.g. Gemma) reject the 'system' role - merge it into the user turn."""
        if "gemma" not in model.lower():
            return messages
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [dict(m) for m in messages if m["role"] != "system"]
        if rest and rest[0]["role"] == "user":
            rest[0]["content"] = f"{system}\n\n{rest[0]['content']}"
        else:
            rest.insert(0, {"role": "user", "content": system})
        return rest


_llm: LLMProvider | None = None


def get_llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = OpenRouterProvider()
    return _llm


def set_llm(provider: LLMProvider | None) -> None:
    """Swap the provider (used by tests, or to plug in another vendor)."""
    global _llm
    _llm = provider
