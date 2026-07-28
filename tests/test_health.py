import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai.llm import llm_status


def test_health_shows_llm_status(mock_llm_available, reset_stores):
    with TestClient(app) as c:
        r = c.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["llm"]["available"] is True


def test_health_offline(mock_llm_offline, reset_stores):
    with TestClient(app) as c:
        r = c.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["llm"]["available"] is False
    assert data["llm"]["last_error"] == "key missing"
