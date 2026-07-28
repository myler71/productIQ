"""ProductIQ API routes — all endpoints in one router."""
from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from app.api.auth import current_username
from app.database.store import Store, ensure_session_cookie, manager
from app.services.ai.chains import ai_ceo_report, ai_recommendations, ai_simulate
from app.services.ai.crew import run_board_meeting
from app.services.ai.llm import llm_status
from app.services.analysis.engine import (
    compute_analytics,
    product_dna,
    product_list,
)
from app.services.memory import store as memory_store
from app.services.research.agent import (
    research_chat,
    research_history as agent_research_history,
    research_report,
)
from app.services.research.mcp_client import tavily_client

router = APIRouter(prefix="/api")


def get_store(request: Request, response: Response) -> Store:
    """Dependency: authenticated users get an isolated per-user store;
    anonymous users share the cookie-scoped demo session store."""
    username = current_username(request)
    if username:
        return manager.get_user_store(username)
    sid = ensure_session_cookie(request, response)
    return manager.get(sid)


@router.get("/health")
def health():
    status = llm_status()
    return {
        "status": "ok",
        "llm": status,
    }


@router.post("/load-sample")
def load_sample(store: Store = Depends(get_store)):
    store.load_sample()
    return {"ok": True, "sample": True,
            "files": [
                {"name": "products.csv", "rows": len(store.products), "valid": len(store.products), "flagged": 0, "rejected": 0},
                {"name": "sales.csv", "rows": len(store.sales), "valid": len(store.sales), "flagged": 0, "rejected": 0},
                {"name": "inventory.csv", "rows": len(store.inventory), "valid": len(store.inventory), "flagged": 0, "rejected": 0},
                {"name": "suppliers.csv", "rows": len(store.suppliers), "valid": len(store.suppliers), "flagged": 0, "rejected": 0},
            ],
            "flags": []}


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...), store: Store = Depends(get_store)):
    raw = {f.filename: await f.read() for f in files}
    return store.load_upload(raw)


@router.get("/analytics")
def analytics(store: Store = Depends(get_store)):
    result = compute_analytics(store)
    memory_store.record_metrics_snapshot(result, label="auto")
    return result


@router.get("/recommendations")
def recommendations(lang: str = "en", store: Store = Depends(get_store)):
    return ai_recommendations(lang, store)


@router.get("/products")
def products(store: Store = Depends(get_store)):
    return product_list(store)


@router.get("/product-dna/{product_id}")
def dna(product_id: str, store: Store = Depends(get_store)):
    result = product_dna(product_id, store)
    return result or {"error": "product not found"}


@router.post("/ceo-report")
def ceo_report(lang: str = "en", store: Store = Depends(get_store)):
    return ai_ceo_report(lang, store)


@router.post("/simulate")
def simulate(payload: dict, store: Store = Depends(get_store)):
    return ai_simulate(payload, store)


@router.post("/board-meeting")
def board_meeting(payload: dict, store: Store = Depends(get_store)):
    """Run a 4-agent board meeting on a product.
    Body: {"product_id": "P001", "lang": "en"}
    """
    return run_board_meeting(payload.get("product_id", ""), payload.get("lang", "en"), store)


# ═══════════════════ Research (Task 1.5) ═══════════════════

@router.get("/research/status")
def research_status():
    return tavily_client.status()


@router.post("/research/chat")
async def research_chat_endpoint(payload: dict, store: Store = Depends(get_store)):
    """Conversational research. Body: {session_id, message, lang}"""
    return await research_chat(
        session_id=payload.get("session_id", "default"),
        message=payload.get("message", ""),
        lang=payload.get("lang", "en"),
        store=store,
    )


@router.get("/research/history")
def research_history_endpoint(session_id: str = "default"):
    return {"session_id": session_id, "history": agent_research_history(session_id)}


@router.post("/research/report")
async def research_report_endpoint(payload: dict, store: Store = Depends(get_store)):
    """Full research pipeline for one product. Body: {product_name|product_id, lang}"""
    name = payload.get("product_name")
    if not name and payload.get("product_id"):
        for p in product_list(store):
            if p["id"] == payload["product_id"]:
                name = p["name"]
                break
    if not name:
        return {"error": "product_name or product_id required"}
    result = await research_report(name, payload.get("lang", "en"), store)
    memory_store.record_product_finding(name, result, result.get("engine", "deterministic"))
    return result


# ═══════════════════════ Memory / History (Task 5a) ═══════════════════════

@router.get("/memory/research-history")
def api_research_history(session_id: str | None = None, limit: int = 100, offset: int = 0):
    return {"entries": memory_store.query_research_history(session_id, limit, offset)}


@router.get("/memory/product-findings")
def api_product_findings(product: str | None = None, limit: int = 100, offset: int = 0):
    return {"entries": memory_store.query_product_findings(product, limit, offset)}


@router.get("/memory/board-decisions")
def api_board_decisions(product_name: str | None = None, limit: int = 100, offset: int = 0):
    return {"entries": memory_store.query_board_decisions(product_name, limit, offset)}


@router.get("/memory/metrics-snapshots")
def api_metrics_snapshots(label: str | None = None, limit: int = 100, offset: int = 0):
    return {"entries": memory_store.query_metrics_snapshots(label, limit, offset)}


@router.get("/memory/diff/{product}")
def api_diff(product: str):
    return {"product": product, "history": memory_store.diff_research_reports(product)}


@router.post("/memory/snapshot")
def api_snapshot(store: Store = Depends(get_store)):
    analytics = compute_analytics(store)
    memory_store.record_metrics_snapshot(analytics, label="manual")
    return {"ok": True, "snapshot_id": 1}


@router.get("/memory/export")
def api_export():
    return {"exported_at": memory_store.EXPORT_PATH.is_file()}
