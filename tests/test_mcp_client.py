"""Tests for the Tavily MCP client — mocked MCP boundary, no live API calls."""
import json
import time

import pytest

from app.services.research import mcp_client as mc
from app.services.research.mcp_client import SearchResult, TavilySearchClient


class FakeContent:
    def __init__(self, text):
        self.text = text


class FakeMCPResult:
    def __init__(self, results):
        self.content = [FakeContent(json.dumps({"results": results}))]


SAMPLE = [
    {"title": "Samsung A56 price in Egypt", "url": "https://eg.example.com/a56",
     "content": "The Galaxy A56 sells for around 5,999 EGP in Cairo.", "score": 0.9,
     "published_date": "2026-07-01"},
    {"title": "No URL item", "url": "", "content": "ignored"},
]


def make_client() -> TavilySearchClient:
    c = TavilySearchClient()
    c._unavailable_reason = None  # pretend key + npx are present
    return c


def test_parsing_maps_fields():
    client = make_client()
    results = client._parse_results(FakeMCPResult(SAMPLE))
    assert len(results) == 1  # item without URL dropped
    r = results[0]
    assert r.title == "Samsung A56 price in Egypt"
    assert r.domain == "eg.example.com"
    assert r.description.startswith("The Galaxy A56")
    assert r.age == "2026-07-01"


def test_parsing_empty_when_no_json():
    client = make_client()
    assert client._parse_results(FakeMCPResult([])) == []


@pytest.mark.asyncio
async def test_search_caches_second_identical_query(monkeypatch):
    client = make_client()
    calls = {"n": 0}

    async def fake_call(tool_args):
        calls["n"] += 1
        return FakeMCPResult(SAMPLE)

    monkeypatch.setattr(client, "_call_tool", fake_call)
    r1 = await client.search("galaxy a56 price egypt", count=3)
    r2 = await client.search("Galaxy A56 price Egypt", count=3)  # same, normalised
    assert calls["n"] == 1
    assert r1.cached is False
    assert r2.cached is True


@pytest.mark.asyncio
async def test_budget_exhaustion(monkeypatch):
    client = make_client()
    client._calls_this_month = mc.RESEARCH_MONTHLY_BUDGET

    async def fake_call(tool_args):
        raise AssertionError("must not call MCP when budget exhausted")

    monkeypatch.setattr(client, "_call_tool", fake_call)
    r = await client.search("anything")
    assert r.available is False
    assert "budget" in r.reason
    assert r.remaining_budget == 0


@pytest.mark.asyncio
async def test_rate_limit(monkeypatch):
    client = make_client()
    client._tokens = 0.0  # bucket empty
    client._bucket_last = time.monotonic()
    r = await client.search("anything fresh")
    assert r.available is False
    assert "rate limited" in r.reason


@pytest.mark.asyncio
async def test_degrades_without_key():
    c = TavilySearchClient()
    c._unavailable_reason = "TAVILY_API_KEY not configured"
    r = await c.search("galaxy a56")
    assert r.available is False
    assert r.reason == "TAVILY_API_KEY not configured"
    assert r.results == []


@pytest.mark.asyncio
async def test_mcp_failure_degrades_gracefully(monkeypatch):
    client = make_client()

    async def boom(tool_args):
        raise RuntimeError("process died")

    monkeypatch.setattr(client, "_call_tool", boom)
    r = await client.search("galaxy a56")
    assert r.available is False
    assert "failed" in r.reason


def test_status_reports_counts():
    client = make_client()
    st = client.status()
    assert st["available"] is True
    assert st["remaining_budget"] == mc.RESEARCH_MONTHLY_BUDGET
