"""Tavily MCP client — live web research for ProductIQ.

Design contract (from the v4 build prompt):
- Spawns `npx tavily-mcp` over stdio via the official MCP Python SDK.
- One long-lived session across calls (no subprocess-per-query), guarded by an
  asyncio.Lock, with lazy reconnect if the process dies.
- In-memory TTL cache (default 6h, normalised query keys) to protect the
  ~1,000/month free-tier quota.
- Token-bucket rate limiter + monthly call counter with graceful budget
  exhaustion (degrades, doesn't error).
- asyncio timeouts on every MCP call — a hung process never blocks a request.
- If TAVILY_API_KEY is missing or Node/npx is unavailable, the whole feature
  degrades cleanly: `available` is False, search returns an honest state.
"""
from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from app.core.config import (
    RESEARCH_CACHE_TTL_HOURS,
    RESEARCH_MONTHLY_BUDGET,
    RESEARCH_TIMEOUT_SECONDS,
    TAVILY_API_KEY,
    TAVILY_MCP_ARGS,
    TAVILY_MCP_COMMAND,
)

TOOL_NAME = "tavily_search"
_BUCKET_CAPACITY = 8.0          # max burst
_BUCKET_REFILL_PER_SEC = 0.2    # ~1 call per 5s sustained


@dataclass
class SearchResult:
    title: str
    url: str
    description: str
    age: str | None = None
    domain: str = ""

    @classmethod
    def from_url(cls, title: str, url: str, description: str,
                 age: str | None = None) -> "SearchResult":
        return cls(title=title, url=url, description=description,
                   age=age, domain=urlparse(url).netloc)


@dataclass
class SearchResponse:
    available: bool
    results: list[SearchResult] = field(default_factory=list)
    cached: bool = False
    reason: str | None = None
    remaining_budget: int | None = None


class TavilySearchClient:
    """Async client for the Tavily MCP server (stdio transport)."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._session = None
        self._exit_stack: AsyncExitStack | None = None
        self._cache: dict[str, tuple[float, list[SearchResult]]] = {}
        self._month = datetime.now().strftime("%Y-%m")
        self._calls_this_month = 0
        self._tokens = _BUCKET_CAPACITY
        self._bucket_last = time.monotonic()
        self._unavailable_reason: str | None = None
        if not TAVILY_API_KEY:
            self._unavailable_reason = "TAVILY_API_KEY not configured"
        elif shutil.which(TAVILY_MCP_COMMAND) is None:
            self._unavailable_reason = f"'{TAVILY_MCP_COMMAND}' not found — Node/npx required"

    # ── availability / status ────────────────────────────────
    @property
    def available(self) -> bool:
        return self._unavailable_reason is None

    def status(self) -> dict:
        return {
            "available": self.available,
            "reason": self._unavailable_reason,
            "calls_this_month": self._calls_this_month,
            "remaining_budget": max(0, RESEARCH_MONTHLY_BUDGET - self._calls_this_month),
            "cached_queries": len(self._cache),
        }

    # ── session lifecycle ────────────────────────────────────
    async def _teardown(self):
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
        self._exit_stack = None
        self._session = None

    async def _ensure_session(self):
        async with self._lock:
            if self._session is not None:
                return self._session
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            stack = AsyncExitStack()
            env = {**os.environ, "TAVILY_API_KEY": TAVILY_API_KEY}
            params = StdioServerParameters(
                command=TAVILY_MCP_COMMAND,
                args=shlex.split(TAVILY_MCP_ARGS),
                env=env,
            )
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await asyncio.wait_for(session.initialize(), timeout=RESEARCH_TIMEOUT_SECONDS)
            self._exit_stack = stack
            self._session = session
            return session

    async def _call_tool(self, tool_args: dict):
        """Call tavily-search with timeout + one reconnect attempt on failure."""
        try:
            session = await self._ensure_session()
            return await asyncio.wait_for(
                session.call_tool(TOOL_NAME, tool_args),
                timeout=RESEARCH_TIMEOUT_SECONDS,
            )
        except Exception:
            await self._teardown()
            session = await self._ensure_session()
            return await asyncio.wait_for(
                session.call_tool(TOOL_NAME, tool_args),
                timeout=RESEARCH_TIMEOUT_SECONDS,
            )

    # ── budget & rate limiting ───────────────────────────────
    def _check_month(self):
        current = datetime.now().strftime("%Y-%m")
        if current != self._month:
            self._month = current
            self._calls_this_month = 0

    def _budget_ok(self) -> bool:
        self._check_month()
        return self._calls_this_month < RESEARCH_MONTHLY_BUDGET

    def _take_token(self) -> bool:
        now = time.monotonic()
        elapsed = now - self._bucket_last
        self._bucket_last = now
        self._tokens = min(_BUCKET_CAPACITY, self._tokens + elapsed * _BUCKET_REFILL_PER_SEC)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    # ── caching ──────────────────────────────────────────────
    def _cache_key(self, query: str, count: int, freshness: str | None) -> str:
        return f"{query.strip().lower()}|{count}|{freshness or ''}"

    def _cache_get(self, key: str) -> list[SearchResult] | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        ts, results = entry
        if (time.time() - ts) > RESEARCH_CACHE_TTL_HOURS * 3600:
            del self._cache[key]
            return None
        return results

    def _cache_put(self, key: str, results: list[SearchResult]):
        self._cache[key] = (time.time(), results)

    # ── main entry ───────────────────────────────────────────
    async def search(self, query: str, count: int = 5,
                     freshness: str | None = None) -> SearchResponse:
        if not self.available:
            return SearchResponse(available=False, reason=self._unavailable_reason)

        key = self._cache_key(query, count, freshness)
        cached = self._cache_get(key)
        if cached is not None:
            return SearchResponse(available=True, results=cached, cached=True,
                                  remaining_budget=max(0, RESEARCH_MONTHLY_BUDGET - self._calls_this_month))

        if not self._budget_ok():
            return SearchResponse(available=False,
                                  reason="monthly research budget exhausted",
                                  remaining_budget=0)
        if not self._take_token():
            return SearchResponse(available=False,
                                  reason="rate limited — try again shortly",
                                  remaining_budget=max(0, RESEARCH_MONTHLY_BUDGET - self._calls_this_month))

        # Tavily takes max_results (not count) and time_range (not freshness)
        tool_args = {"query": query, "max_results": count}
        if freshness:
            tool_args["time_range"] = freshness

        try:
            result = await self._call_tool(tool_args)
        except Exception as e:
            return SearchResponse(available=False,
                                  reason=f"research call failed: {type(e).__name__}: {e}",
                                  remaining_budget=max(0, RESEARCH_MONTHLY_BUDGET - self._calls_this_month))

        self._calls_this_month += 1
        results = self._parse_results(result)
        self._cache_put(key, results)
        return SearchResponse(available=True, results=results, cached=False,
                              remaining_budget=max(0, RESEARCH_MONTHLY_BUDGET - self._calls_this_month))

    # ── parsing ──────────────────────────────────────────────
    def _parse_results(self, mcp_result) -> list[SearchResult]:
        """Parse MCP tool content into SearchResults. Retains source URLs always.

        Handles both shapes the Tavily MCP server emits:
        - JSON payload: {"results": [{title, url, content, published_date}, ...]}
        - Formatted text: blocks of "Title: ... / URL: ... / Content: ..."
        """
        import re

        for item in getattr(mcp_result, "content", []) or []:
            text = getattr(item, "text", None)
            if not text:
                continue

            # 1) Try JSON first
            try:
                payload = json.loads(text)
                items = payload.get("results") or payload.get("data") or []
                out = []
                for it in items:
                    url = it.get("url", "")
                    if not url:
                        continue
                    out.append(SearchResult.from_url(
                        title=it.get("title", ""), url=url,
                        description=(it.get("content") or "")[:400],
                        age=it.get("published_date") or it.get("age")))
                if out:
                    return out
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

            # 2) Formatted-text blocks: Title:/URL:/Content:
            out = []
            blocks = re.split(r"\n\s*\n", text)
            current: dict[str, str] = {}
            for block in blocks:
                for line in block.splitlines():
                    if line.startswith("Title:"):
                        if current.get("url"):
                            out.append(self._mk_result(current))
                        current = {"title": line[6:].strip()}
                    elif line.startswith("URL:"):
                        current["url"] = line[4:].strip()
                    elif line.startswith("Content:"):
                        current["content"] = line[8:].strip()
                    elif current and "content" in current:
                        current["content"] += " " + line.strip()
            if current.get("url"):
                out.append(self._mk_result(current))
            if out:
                return out
        return []

    @staticmethod
    def _mk_result(parts: dict) -> "SearchResult":
        return SearchResult.from_url(
            title=parts.get("title", ""),
            url=parts.get("url", ""),
            description=parts.get("content", "")[:400])

    async def aclose(self):
        await self._teardown()


# Singleton used by the research agent
tavily_client = TavilySearchClient()
