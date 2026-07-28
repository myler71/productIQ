"""Tests for the LLM service + provenance."""
import pytest

from app.services.ai import llm as llm_module
from app.services.ai.llm import extract_json_block, invoke_llm, llm_status


def test_llm_status_offline_when_key_empty(monkeypatch):
    monkeypatch.setattr(llm_module, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_module, "_llm", None)
    status = llm_status()
    assert status["configured"] is False
    assert status["available"] is False
    assert status["last_error"] is not None


def test_invoke_llm_returns_fallback_when_unconfigured(monkeypatch):
    monkeypatch.setattr(llm_module, "GROQ_API_KEY", "")
    monkeypatch.setattr(llm_module, "_llm", None)
    result = invoke_llm("hello", fallback="fallback-text")
    assert result["content"] == "fallback-text"
    assert result["engine"] == "deterministic"
    assert result["error"] is not None


def test_extract_json_block_parses_object():
    text = 'Some text before {"a": 1, "b": [2]} after'
    parsed = extract_json_block(text)
    assert parsed == {"a": 1, "b": [2]}


def test_extract_json_block_returns_none_for_invalid():
    assert extract_json_block("no json here") is None
