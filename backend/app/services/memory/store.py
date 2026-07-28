"""Persistent memory for ProductIQ — SQLite-backed, auto-exports to memory.json.

Tables:
  - research_history: research conversations (user messages, assistant replies, sources)
  - product_findings: structured research reports per product
  - board_decisions: board meeting transcripts and verdicts
  - metrics_snapshots: periodic analytics snapshots for trend comparison
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock

from app.core.config import SQLITE_DIR

DB_PATH = SQLITE_DIR / "memory.db"
EXPORT_PATH = SQLITE_DIR / "memory.json"
_lock = Lock()


def _connect() -> sqlite3.Connection:
    SQLITE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_tables() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS research_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                content_ar TEXT DEFAULT '',
                sources TEXT DEFAULT '[]',
                engine TEXT DEFAULT 'deterministic',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS product_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                report_json TEXT NOT NULL,
                engine TEXT DEFAULT 'deterministic',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS board_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                context TEXT DEFAULT '',
                transcript_json TEXT NOT NULL,
                verdict TEXT DEFAULT '',
                engine TEXT DEFAULT 'deterministic',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metrics_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_json TEXT NOT NULL,
                label TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_rh_session ON research_history(session_id);
            CREATE INDEX IF NOT EXISTS idx_pf_product ON product_findings(product);
            CREATE INDEX IF NOT EXISTS idx_bd_product ON board_decisions(product_name);
            CREATE INDEX IF NOT EXISTS idx_ms_created ON metrics_snapshots(created_at);
        """)
        conn.commit()


def _export_json() -> None:
    """Write a human-readable memory.json with all tables."""
    with _lock:
        data = {
            "research_history": query_research_history(limit=50),
            "product_findings": query_product_findings(limit=50),
            "board_decisions": query_board_decisions(limit=50),
            "metrics_snapshots": query_metrics_snapshots(limit=50),
            "exported_at": datetime.utcnow().isoformat(),
        }
        EXPORT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════ Research History ═══════════════════════


def record_research_message(session_id: str, role: str, content: str,
                            content_ar: str = "", sources: list | None = None,
                            engine: str = "deterministic") -> int:
    init_tables()
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO research_history (session_id, role, content, content_ar, sources, engine, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, role, content, content_ar,
             json.dumps(sources or [], ensure_ascii=False),
             engine, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row_id = cur.lastrowid
    _export_json()
    return row_id


def query_research_history(session_id: str | None = None,
                           limit: int = 100, offset: int = 0) -> list[dict]:
    init_tables()
    with _connect() as conn:
        if session_id:
            rows = conn.execute(
                "SELECT * FROM research_history WHERE session_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (session_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM research_history ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d.get("sources", "[]"))
        result.append(d)
    return result


# ═══════════════════════ Product Findings ═══════════════════════


def record_product_finding(product: str, report: dict, engine: str = "deterministic") -> int:
    init_tables()
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO product_findings (product, report_json, engine, created_at) VALUES (?, ?, ?, ?)",
            (product, json.dumps(report, ensure_ascii=False), engine, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row_id = cur.lastrowid
    _export_json()
    return row_id


def query_product_findings(product: str | None = None,
                           limit: int = 100, offset: int = 0) -> list[dict]:
    init_tables()
    with _connect() as conn:
        if product:
            rows = conn.execute(
                "SELECT * FROM product_findings WHERE product = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (product, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM product_findings ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["report"] = json.loads(d.pop("report_json", "{}"))
        result.append(d)
    return result


# ═══════════════════════ Board Decisions ═══════════════════════


def record_board_decision(product_name: str, context: str, transcript: list,
                          verdict: str = "", engine: str = "deterministic") -> int:
    init_tables()
    if not isinstance(verdict, str):
        verdict = str(verdict)
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO board_decisions (product_name, context, transcript_json, verdict, engine, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (product_name, context,
             json.dumps(transcript, ensure_ascii=False),
             verdict, engine, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row_id = cur.lastrowid
    _export_json()
    return row_id


def query_board_decisions(product_name: str | None = None,
                          limit: int = 100, offset: int = 0) -> list[dict]:
    init_tables()
    with _connect() as conn:
        if product_name:
            rows = conn.execute(
                "SELECT * FROM board_decisions WHERE product_name = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (product_name, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM board_decisions ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["transcript"] = json.loads(d.pop("transcript_json", "[]"))
        result.append(d)
    return result


# ═══════════════════════ Metrics Snapshots ═══════════════════════


def record_metrics_snapshot(analytics: dict, label: str = "") -> int:
    init_tables()
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO metrics_snapshots (snapshot_json, label, created_at) VALUES (?, ?, ?)",
            (json.dumps(analytics, ensure_ascii=False), label, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row_id = cur.lastrowid
    _export_json()
    return row_id


def query_metrics_snapshots(label: str | None = None,
                            limit: int = 100, offset: int = 0) -> list[dict]:
    init_tables()
    with _connect() as conn:
        if label:
            rows = conn.execute(
                "SELECT * FROM metrics_snapshots WHERE label = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (label, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM metrics_snapshots ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["snapshot"] = json.loads(d.pop("snapshot_json", "{}"))
        result.append(d)
    return result


# ═══════════════════════ Diff / Compare ═══════════════════════


def diff_research_reports(product: str) -> list[dict]:
    """Return chronologically ordered reports for a product, with diffs against the previous."""
    reports = query_product_findings(product=product, limit=20)
    reports.reverse()
    result = []
    prev = None
    for r in reports:
        entry = {"id": r["id"], "created_at": r["created_at"], "engine": r["engine"],
                 "report": r["report"]}
        if prev:
            entry["diff_summary"] = _summarize_diff(prev, r["report"])
        else:
            entry["diff_summary"] = "Initial report"
        result.append(entry)
        prev = r["report"]
    result.reverse()
    return result


def _summarize_diff(before: dict, after: dict) -> dict:
    """Compare two report dicts and return what changed."""
    diff = {}
    for key in ("confidence", "recommended_action", "summary_en", "summary_ar"):
        b = before.get(key)
        a = after.get(key)
        if b != a:
            diff[key] = {"before": str(b)[:200], "after": str(a)[:200]}
    for key in ("price_landscape", "competitors", "demand_signals"):
        b_len = len(before.get(key, []))
        a_len = len(after.get(key, []))
        if b_len != a_len:
            diff[f"{key}_count"] = {"before": b_len, "after": a_len}
    return diff


# ═══════════════════════ Init on import ═══════════════════════

init_tables()
