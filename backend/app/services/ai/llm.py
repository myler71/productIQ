"""LLM service — LangChain + Groq, with deterministic fallback.
If the API key is missing or the call fails, the app degrades to
rule-based outputs so the demo always works.
"""
from app.core.config import GROQ_API_KEY, GROQ_MODEL

_llm = None


def get_llm():
    """Lazy-init the Groq chat model. Returns None if unavailable."""
    global _llm
    if _llm is not None:
        return _llm
    if not GROQ_API_KEY:
        return None
    try:
        from langchain_groq import ChatGroq
        _llm = ChatGroq(model=GROQ_MODEL, temperature=0.2, api_key=GROQ_API_KEY)
        return _llm
    except Exception:
        return None
