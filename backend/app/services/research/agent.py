"""Research agent — conversational market intelligence.

Pipeline for a research request:
  1. Plan      — LLM turns the question into 3-5 Egyptian-biased search queries
  2. Search    — run them through the Tavily MCP client, dedupe by URL
  3. Extract   — LLM pulls structured facts from snippets, each tagged with source URL
  4. Synthesise— bilingual report (summary, price landscape, competitors,
                 sentiment, risks, action, sources, confidence)
  5. Cross-reference — join web findings against the user's internal figures
                 (cost, price, margin, velocity, stock) and highlight gaps.

Hard rules honoured here:
- Every external claim cites a source URL (no citation, no claim).
- The LLM never invents prices — if search returns nothing usable, we say so.
- Web-sourced facts and your-data facts are kept separate in the payload.
"""
from __future__ import annotations

import asyncio
import difflib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from app.services.ai.llm import extract_json_block, invoke_llm, llm_status
from app.services.analysis.engine import product_list
from app.services.research.mcp_client import SearchResult, tavily_client


# ── conversation memory (in-process + persisted in SQLite via memory store) ──
from app.services.memory.store import record_research_message, record_product_finding

_CONVERSATIONS: dict[str, list[dict]] = {}


@dataclass
class ResearchReport:
    product: str
    summary_en: str = ""
    summary_ar: str = ""
    price_landscape: list[dict] = field(default_factory=list)   # [{point, currency, source_url}]
    competitors: list[dict] = field(default_factory=list)       # [{name, note, source_url}]
    demand_signals: list[dict] = field(default_factory=list)    # [{signal, source_url}]
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    recommended_action: str = ""
    sources: list[dict] = field(default_factory=list)           # [{n, url, title}]
    confidence: int = 0
    confidence_basis: str = ""
    internal_match: dict | None = None                          # your-data facts
    gaps: list[str] = field(default_factory=list)               # cross-reference findings
    engine: str = "deterministic"

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════ pipeline steps ══════════════════════════

def _plan_queries(question: str, product_hint: str | None, lang: str) -> list[str]:
    """LLM plans 3-5 targeted queries; deterministic fallback if offline."""
    prompt = f"""You are planning web research for an Egyptian retailer.
Question: {question}
Product context: {product_hint or 'general market'}

Return ONLY valid JSON: {{"queries": ["q1", "q2", "q3"]}}
Rules: 3-5 queries, each targeting a different angle: current price in Egypt (EGP),
competitors, customer reviews/sentiment, market trend, local availability.
Bias queries toward Egyptian market terms and EGP."""
    result = invoke_llm(prompt, parser=extract_json_block)
    if result["engine"] == "llm" and isinstance(result.get("content"), dict):
        queries = result["content"].get("queries")
        if isinstance(queries, list) and queries:
            return [str(q) for q in queries[:5]]
    # deterministic fallback
    base = product_hint or question
    return [
        f"{base} price in Egypt EGP",
        f"{base} competitors Egypt market",
        f"{base} reviews customer feedback",
        f"{base} availability Egypt stores",
    ]


async def _run_searches(queries: list[str], count: int = 4) -> tuple[list[SearchResult], list[str]]:
    """Run queries through Tavily, dedupe by URL. Returns (results, notes)."""
    notes = []
    if not tavily_client.available:
        return [], [tavily_client.status()["reason"] or "research unavailable"]
    seen: set[str] = set()
    results: list[SearchResult] = []
    for q in queries:
        resp = await tavily_client.search(q, count=count)
        if not resp.available:
            notes.append(resp.reason or f"search failed: {q}")
            continue
        for r in resp.results:
            if r.url not in seen:
                seen.add(r.url)
                results.append(r)
    return results, notes


def _internal_cross_reference(product_hint: str | None, store=None) -> tuple[dict | None, dict | None]:
    """Fuzzy-match the research subject against the user's own catalog."""
    if not product_hint:
        return None, None
    products = product_list(store)
    names = [p["name"] for p in products]
    match = difflib.get_close_matches(product_hint, names, n=1, cutoff=0.4)
    if not match:
        return None, None
    internal = next(p for p in products if p["name"] == match[0])
    return internal, {"matched_name": match[0]}


def _synthesize(question: str, results: list[SearchResult], internal: dict | None,
                lang: str) -> dict:
    """LLM synthesises a cited report; deterministic fallback keeps citations."""
    sources = [{"n": i + 1, "url": r.url, "title": r.title} for i, r in enumerate(results)]
    if not results:
        return {
            "summary_en": "No reliable market data found — web research returned nothing usable. Not inventing figures.",
            "summary_ar": "لم يتم العثور على بيانات موثوقة — البحث على الويب لم يُرجع نتائج قابلة للاستخدام. لا نختلق أرقاماً.",
            "price_landscape": [], "competitors": [], "demand_signals": [],
            "risks": ["No external data available"], "opportunities": [],
            "recommended_action": "Retry research later or add data manually.",
            "sources": [], "confidence": 0,
            "confidence_basis": "No sources retrieved",
            "engine": "deterministic",
        }

    snippets = "\n".join(
        f"[{i+1}] {r.title} ({r.url})\n{r.description}" for i, r in enumerate(results)
    )
    internal_note = ""
    if internal:
        internal_note = (f"\nThe retailer's internal data for a matching product: "
                         f"name={internal['name']}, price={internal['price']} EGP.")

    prompt = f"""You are a market research analyst for an Egyptian retailer.
Question: {question}
{internal_note}

Web sources (cite every claim with [n] matching the source number):
{snippets}

Return ONLY valid JSON:
{{
  "summary_en": "2-3 sentences, plain text, claims carry [n] citations",
  "summary_ar": "Arabic version of the summary, keep [n] citations",
  "price_landscape": [{{"point": "e.g. 21,499 EGP at noon", "source_n": 1}}],
  "competitors": [{{"name": "...", "note": "...", "source_n": 1}}],
  "demand_signals": [{{"signal": "...", "source_n": 1}}],
  "risks": ["..."], "opportunities": ["..."],
  "recommended_action": "one clear action",
  "confidence": 0-100,
  "confidence_basis": "why this confidence"
}}
RULES: never invent a price. Every price/competitor/signal must have source_n.
If sources lack data, leave the list empty rather than guessing."""

    result = invoke_llm(prompt, parser=extract_json_block)
    if result["engine"] == "llm" and isinstance(result.get("content"), dict):
        data = result["content"]
        data["sources"] = sources
        data["engine"] = "llm"
        return _ground_citations(data, len(results))
    # deterministic fallback: cite what we have, no invented claims
    return {
        "summary_en": f"Found {len(results)} relevant sources. Key findings are listed with citations below.",
        "summary_ar": f"تم العثور على {len(results)} مصادر ذات صلة. النتائج الرئيسية مذكورة مع المراجع أدناه.",
        "price_landscape": [
            {"point": f"{r.title}: {r.description[:150]}", "source_n": i + 1}
            for i, r in enumerate(results[:3])
        ],
        "competitors": [], "demand_signals": [
            {"signal": r.description[:150], "source_n": i + 1}
            for i, r in enumerate(results[:3])
        ],
        "risks": [], "opportunities": [],
        "recommended_action": "Review the cited sources for details.",
        "sources": sources,
        "confidence": 55,
        "confidence_basis": "Deterministic summary of retrieved sources (LLM offline).",
        "engine": "deterministic",
    }


def _ground_citations(data: dict, max_n: int) -> dict:
    """Drop any list item whose citation number is out of range (hallucinated source)."""
    def clean(items, key="source_n"):
        if not isinstance(items, list):
            return []
        return [it for it in items
                if isinstance(it, dict) and isinstance(it.get(key), int)
                and 1 <= it[key] <= max_n]
    data["price_landscape"] = clean(data.get("price_landscape"))
    data["competitors"] = clean(data.get("competitors"))
    data["demand_signals"] = clean(data.get("demand_signals"))
    for k in ("risks", "opportunities"):
        if not isinstance(data.get(k), list):
            data[k] = []
    data["risks"] = [str(r) for r in data["risks"]]
    data["opportunities"] = [str(o) for o in data["opportunities"]]
    return data


def _compute_gaps(report: dict, internal: dict | None) -> list[str]:
    """Cross-reference web price points vs internal price/margin."""
    gaps = []
    if not internal:
        return gaps
    import re
    internal_price = internal.get("price")
    for item in report.get("price_landscape", []):
        point = str(item.get("point", ""))
        nums = re.findall(r"([\d,]+)\s*EGP", point, re.IGNORECASE)
        if not nums:
            nums = re.findall(r"EGP\s*([\d,]+)", point, re.IGNORECASE)
        if not nums:
            continue
        try:
            market_price = float(nums[0].replace(",", ""))
        except ValueError:
            continue
        if internal_price and market_price > 0:
            diff = (internal_price - market_price) / market_price * 100
            if abs(diff) >= 3:
                direction = "above" if diff > 0 else "below"
                src = item.get("source_n")
                gaps.append(f"Your price ({internal_price:,.0f} EGP) is {abs(diff):.0f}% {direction} "
                            f"the observed market point {market_price:,.0f} EGP [{src}].")
    return gaps


# ══════════════════════════ public API ══════════════════════════

async def research_report(product_name: str, lang: str = "en", store=None) -> dict:
    """Full pipeline for one product. Returns a structured report dict."""
    queries = _plan_queries(f"Should I stock and how should I price {product_name}?", product_name, lang)
    results, notes = await _run_searches(queries)
    internal, match = _internal_cross_reference(product_name, store)
    data = _synthesize(f"Should I stock and how should I price {product_name} in Egypt?",
                       results, internal, lang)
    gaps = _compute_gaps(data, internal)
    report = ResearchReport(
        product=product_name,
        summary_en=data.get("summary_en", ""),
        summary_ar=data.get("summary_ar", ""),
        price_landscape=data.get("price_landscape", []),
        competitors=data.get("competitors", []),
        demand_signals=data.get("demand_signals", []),
        risks=data.get("risks", []),
        opportunities=data.get("opportunities", []),
        recommended_action=data.get("recommended_action", ""),
        sources=data.get("sources", []),
        confidence=int(data.get("confidence", 0) or 0),
        confidence_basis=data.get("confidence_basis", ""),
        internal_match=internal,
        gaps=gaps,
        engine=data.get("engine", "deterministic"),
    )
    out = report.to_dict()
    out["queries"] = queries
    out["notes"] = notes
    out["matched_product"] = match
    return out


async def research_chat(session_id: str, message: str, lang: str = "en", store=None) -> dict:
    """Conversational research: keeps history, runs the pipeline, replies with citations."""
    history = _CONVERSATIONS.setdefault(session_id, [])
    history.append({"role": "user", "content": message, "ts": datetime.utcnow().isoformat()})

    # persist user message
    record_research_message(session_id, "user", message)

    report = await research_report(message, lang, store)

    status = llm_status()
    reply = {
        "role": "assistant",
        "content_en": report["summary_en"],
        "content_ar": report["summary_ar"],
        "ts": datetime.utcnow().isoformat(),
        "sources": report["sources"],
        "engine": report["engine"],
        "research_available": tavily_client.available,
    }
    history.append(reply)

    # persist assistant reply
    record_research_message(
        session_id, "assistant", report["summary_en"],
        content_ar=report["summary_ar"],
        sources=report.get("sources", []),
        engine=report.get("engine", "deterministic"),
    )
    # persist product finding too
    product_hint = message[:80]
    record_product_finding(product_hint, report, report.get("engine", "deterministic"))

    return {
        "session_id": session_id,
        "reply": reply,
        "report": report,
        "engine": report["engine"],
    }


def research_history(session_id: str) -> list[dict]:
    return _CONVERSATIONS.get(session_id, [])
