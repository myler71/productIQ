"""LLM service — Groq init, status, invoke with deterministic fallback.
Tracks last_error so the UI can explain why it is in rule-based mode.
"""
import os
from typing import Callable

from app.core.config import GROQ_API_KEY, GROQ_MODEL

_llm = None
_last_error: str | None = None


def _init_llm():
    """Lazy-init the Groq chat model."""
    global _llm, _last_error
    if _llm is not None:
        return _llm
    if not GROQ_API_KEY:
        _last_error = "GROQ_API_KEY not configured"
        return None
    try:
        from langchain_groq import ChatGroq
        _llm = ChatGroq(model=GROQ_MODEL, temperature=0.2, api_key=GROQ_API_KEY)
        _last_error = None
        return _llm
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e}"
        return None


def llm_status() -> dict:
    """Return configuration/availability state."""
    configured = bool(GROQ_API_KEY)
    llm = _init_llm()
    return {
        "configured": configured,
        "available": llm is not None,
        "last_error": _last_error,
        "model": GROQ_MODEL if configured else None,
    }


def invoke_llm(
    prompt: str,
    *,
    temperature: float = 0.2,
    fallback: str | None = None,
    parser: Callable[[str], dict | None] | None = None,
) -> dict:
    """Invoke the LLM. Returns a dict with content, engine, and error.

    - engine="llm" when LLM produced the content
    - engine="deterministic" when LLM was unavailable or call failed
    - parser: optional function that extracts JSON from the response; if it fails,
      the raw content is returned with engine="deterministic+llm" and the error.
    """
    global _last_error
    llm = _init_llm()
    if llm is None:
        return {
            "content": fallback or "LLM unavailable — deterministic fallback used.",
            "engine": "deterministic",
            "error": _last_error,
        }
    try:
        llm.temperature = temperature
        resp = llm.invoke(prompt)
        raw = resp.content.strip()
        if parser:
            parsed = parser(raw)
            if parsed is not None:
                return {"content": parsed, "engine": "llm", "error": None}
            # parser failed but raw text may be useful
            return {"content": raw, "engine": "deterministic+llm", "error": "JSON parse failed"}
        return {"content": raw, "engine": "llm", "error": None}
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e}"
        return {
            "content": fallback or "LLM call failed — deterministic fallback used.",
            "engine": "deterministic",
            "error": _last_error,
        }


def extract_json_block(text: str) -> dict | None:
    """Best-effort extract the first JSON object from a string."""
    import json as _json
    import re as _re
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    match = _re.search(r"\{.*\}", text, _re.DOTALL)
    if not match:
        return None
    try:
        return _json.loads(match.group(0))
    except Exception:
        return None
