"""Tests for the research agent — mocked LLM + mocked Tavily search."""
import pytest

from app.database.store import Store
from app.services.research import agent as ag
from app.services.research.mcp_client import SearchResponse, SearchResult
from fastapi.testclient import TestClient
from app.main import app


FAKE_RESULTS = [
    SearchResult.from_url("A56 price Egypt", "https://eg.pricena.com/a56",
                          "Best price EGP 21499 at noon with free shipping."),
    SearchResult.from_url("A56 on Amazon Egypt", "https://www.amazon.eg/a56",
                          "Samsung Galaxy A56 256GB available."),
    SearchResult.from_url("A56 dubizzle", "https://www.dubizzle.com.eg/a56",
                          "Samsung A56 prices range EGP 18,000 to 23,500 in Cairo."),
]


@pytest.fixture
def mock_search(monkeypatch):
    ag.tavily_client._unavailable_reason = None

    async def fake_search(query, count=4, freshness=None):
        return SearchResponse(available=True, results=FAKE_RESULTS, cached=False,
                              remaining_budget=899)
    monkeypatch.setattr(ag.tavily_client, "search", fake_search)
    yield


@pytest.fixture
def mock_search_empty(monkeypatch):
    ag.tavily_client._unavailable_reason = None

    async def fake_search(query, count=4, freshness=None):
        return SearchResponse(available=True, results=[], cached=False)
    monkeypatch.setattr(ag.tavily_client, "search", fake_search)
    yield


def test_plan_queries_fallback_deterministic(mock_llm_offline, reset_stores):
    queries = ag._plan_queries("price of Galaxy A56", "Galaxy A56", "en")
    assert 3 <= len(queries) <= 5
    assert any("Egypt" in q for q in queries)


def test_ground_citations_drops_hallucinated():
    data = {
        "price_landscape": [
            {"point": "21,499 EGP at noon", "source_n": 1},
            {"point": "hallucinated price", "source_n": 99},
            {"point": "no citation"},
        ],
        "competitors": [{"name": "X", "source_n": 2}],
        "demand_signals": [],
        "risks": ["r"], "opportunities": ["o"],
    }
    cleaned = ag._ground_citations(data, max_n=3)
    assert len(cleaned["price_landscape"]) == 1
    assert cleaned["price_landscape"][0]["source_n"] == 1
    assert len(cleaned["competitors"]) == 1


def test_compute_gaps_finds_price_gap():
    report = {"price_landscape": [{"point": "Best price EGP 20,000 at noon", "source_n": 1}]}
    internal = {"price": 23900.0, "name": "X"}
    gaps = ag._compute_gaps(report, internal)
    assert gaps
    assert "above" in gaps[0]
    assert "[1]" in gaps[0]


def test_compute_gaps_no_internal_returns_empty():
    assert ag._compute_gaps({"price_landscape": []}, None) == []


@pytest.mark.asyncio
async def test_report_pipeline_with_sources(mock_llm_available, mock_search, reset_stores):
    store = Store()
    store.load_sample()
    report = await ag.research_report("Samsung Galaxy A56", "en", store)
    assert report["sources"], "report must carry sources"
    assert len(report["sources"]) == 3
    assert report["queries"], "pipeline must plan queries"


@pytest.mark.asyncio
async def test_report_no_results_honest(mock_llm_available, mock_search_empty, reset_stores):
    report = await ag.research_report("Nonexistent Gadget X9000", "en", Store())
    assert "No reliable market data" in report["summary_en"]
    assert report["price_landscape"] == []
    assert report["confidence"] == 0


@pytest.mark.asyncio
async def test_chat_keeps_history(mock_llm_available, mock_search, reset_stores):
    store = Store()
    store.load_sample()
    r = await ag.research_chat("s1", "Samsung Galaxy A56 price?", "en", store)
    assert r["reply"]["sources"]
    history = ag.research_history("s1")
    assert len(history) == 2  # user + assistant


def test_research_endpoints(mock_llm_available, mock_search, reset_stores):
    with TestClient(app) as c:
        r = c.post("/api/research/report", json={"product_name": "Samsung Galaxy A56"})
        assert r.status_code == 200
        assert "sources" in r.json()

        r2 = c.post("/api/research/chat", json={"session_id": "t1", "message": "A56 price?"})
        assert r2.status_code == 200
        assert r2.json()["reply"]["sources"]

        r3 = c.get("/api/research/history", params={"session_id": "t1"})
        assert len(r3.json()["history"]) == 2


def test_research_status_endpoint(mock_llm_available, reset_stores):
    with TestClient(app) as c:
        r = c.get("/api/research/status")
        assert r.status_code == 200
        assert "available" in r.json()
