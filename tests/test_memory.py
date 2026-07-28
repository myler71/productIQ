"""Tests for the persistent memory store (Task 5a)."""
import pytest
from fastapi.testclient import TestClient

from app.database.store import manager
from app.main import app
from app.services.memory import store as mem


@pytest.fixture(autouse=True)
def clean_memory():
    """Wipe memory DB between tests."""
    mem.init_tables()
    with mem._connect() as conn:
        for table in ("research_history", "product_findings", "board_decisions", "metrics_snapshots"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    if mem.EXPORT_PATH.exists():
        mem.EXPORT_PATH.unlink()
    yield


def test_record_and_query_research_history():
    rid = mem.record_research_message("s1", "user", "hello", engine="llm")
    assert rid > 0
    entries = mem.query_research_history("s1")
    assert len(entries) == 1
    assert entries[0]["role"] == "user"
    assert entries[0]["content"] == "hello"
    assert entries[0]["engine"] == "llm"


def test_record_and_query_product_findings():
    report = {"summary_en": "good product", "confidence": 85}
    fid = mem.record_product_finding("Widget X", report, engine="deterministic")
    assert fid > 0
    entries = mem.query_product_findings("Widget X")
    assert len(entries) == 1
    assert entries[0]["product"] == "Widget X"
    assert entries[0]["report"]["summary_en"] == "good product"


def test_record_and_query_board_decisions():
    transcript = [{"role_en": "CFO", "analysis": "good margin"}]
    bid = mem.record_board_decision("Product A", "context str", transcript, verdict="approve")
    assert bid > 0
    entries = mem.query_board_decisions("Product A")
    assert len(entries) == 1
    assert entries[0]["verdict"] == "approve"
    assert len(entries[0]["transcript"]) == 1


def test_record_and_query_metrics_snapshots():
    analytics = {"kpis": {"revenue": 100000, "profit": 20000, "margin": 20.0, "turnover": 8.0}}
    sid = mem.record_metrics_snapshot(analytics, label="auto")
    assert sid > 0
    entries = mem.query_metrics_snapshots("auto")
    assert len(entries) == 1
    assert entries[0]["snapshot"]["kpis"]["revenue"] == 100000


def test_export_json_created():
    mem.record_research_message("s1", "user", "test")
    assert mem.EXPORT_PATH.exists()
    import json
    data = json.loads(mem.EXPORT_PATH.read_text(encoding="utf-8"))
    assert "research_history" in data
    assert "exported_at" in data


def test_diff_research_reports():
    mem.record_product_finding("Widget X", {"summary_en": "v1", "confidence": 50})
    mem.record_product_finding("Widget X", {"summary_en": "v2", "confidence": 80})
    history = mem.diff_research_reports("Widget X")
    assert len(history) >= 2
    # newest entry (index 0) should have a real diff
    newest = history[0]
    assert "diff_summary" in newest
    assert newest["diff_summary"] != "Initial report"


def test_research_history_empty_session():
    assert mem.query_research_history("nonexistent") == []


def test_memory_endpoints_produce_json(client):
    with TestClient(app) as c:
        r = c.get("/api/memory/research-history")
        assert r.status_code == 200
        assert "entries" in r.json()

        r2 = c.get("/api/memory/product-findings")
        assert r2.status_code == 200
        assert "entries" in r2.json()

        r3 = c.get("/api/memory/board-decisions")
        assert r3.status_code == 200
        assert "entries" in r3.json()

        r4 = c.get("/api/memory/metrics-snapshots")
        assert r4.status_code == 200
        assert "entries" in r4.json()


def test_memory_diff_endpoint(client):
    with TestClient(app) as c:
        r = c.get("/api/memory/diff/Samsung")
        assert r.status_code == 200
        assert "history" in r.json()


def test_snapshot_endpoint(client):
    with TestClient(app) as c:
        r = c.post("/api/memory/snapshot")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True


def test_auto_record_on_analytics(client):
    """Calling analytics auto-records a metrics snapshot."""
    with TestClient(app) as c:
        c.get("/api/analytics")
    entries = mem.query_metrics_snapshots("auto")
    assert len(entries) >= 1


def test_auto_record_on_board_meeting(client):
    """Running a board meeting auto-records a board decision."""
    with TestClient(app) as c:
        c.post("/api/board-meeting", json={"product_id": "P001", "lang": "en"})
    entries = mem.query_board_decisions("Samsung Galaxy A56")
    assert len(entries) >= 1
