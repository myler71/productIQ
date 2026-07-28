"""Pytest configuration and fixtures for ProductIQ."""
import pytest
from fastapi.testclient import TestClient

from app.database.store import manager
from app.main import app


def _fake_llm_status():
    return {"configured": True, "available": True, "last_error": None, "model": "mock-model"}


def _fake_invoke(prompt, **kwargs):
    # Recommendations
    if "recommendations" in prompt or "Recommendations" in prompt:
        return {
            "content": {
                "summary_en": "mock summary", "summary_ar": "ملخص زائف",
                "recommendations": [
                    {"product": "A", "product_ar": "أ", "action": "restock",
                     "reason_en": "r1", "reason_ar": "ر1", "confidence": 80}
                ]
            },
            "engine": "llm",
            "error": None,
        }
    # CEO report
    if "CEO" in prompt or "action_items" in prompt:
        return {
            "content": {
                "summary_en": "mock ceo", "summary_ar": "ملخص تنفيذي زائف",
                "action_items_en": ["a"], "action_items_ar": ["أ"]
            },
            "engine": "llm",
            "error": None,
        }
    # Generic fallback
    return {"content": "mock prose", "engine": "llm", "error": None}


def _fake_llm_status_offline():
    return {"configured": False, "available": False, "last_error": "key missing", "model": None}


def _fake_invoke_offline(prompt, **kwargs):
    return {"content": kwargs.get("fallback", "fallback"), "engine": "deterministic", "error": "key missing"}


def _apply_llm_patches(monkeypatch, available: bool):
    """Patch the LLM functions in every module that imported them."""
    if available:
        inv = _fake_invoke
        st = _fake_llm_status
    else:
        inv = _fake_invoke_offline
        st = _fake_llm_status_offline
    monkeypatch.setattr("app.services.ai.llm.invoke_llm", inv)
    monkeypatch.setattr("app.services.ai.chains.invoke_llm", inv)
    monkeypatch.setattr("app.services.ai.crew.invoke_llm", inv)
    monkeypatch.setattr("app.services.ai.llm.llm_status", st)
    monkeypatch.setattr("app.api.routes.llm_status", st)


@pytest.fixture
def reset_stores():
    """Reset the in-memory store manager between tests."""
    manager._stores.clear()
    manager.get("anonymous").load_sample()
    yield
    manager._stores.clear()


@pytest.fixture
def mock_llm_available(monkeypatch):
    """Pretend the LLM is available and returns canned structured responses."""
    _apply_llm_patches(monkeypatch, True)


@pytest.fixture
def mock_llm_offline(monkeypatch):
    """Pretend the LLM key is missing so all AI endpoints fall back to deterministic."""
    _apply_llm_patches(monkeypatch, False)


@pytest.fixture
def client(mock_llm_available, reset_stores):
    """TestClient with default LLM available."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_offline(mock_llm_offline, reset_stores):
    """TestClient with LLM unavailable."""
    with TestClient(app) as c:
        yield c
