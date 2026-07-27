"""ProductIQ API routes — all endpoints in one router."""
from fastapi import APIRouter, File, UploadFile

from app.database.store import store
from app.services.ai.chains import ai_ceo_report, ai_recommendations, ai_simulate
from app.services.analysis.engine import (
    compute_analytics,
    product_dna,
    product_list,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok", "data_source": store.source, "llm": "groq"}


@router.post("/load-sample")
def load_sample():
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
async def upload(files: list[UploadFile] = File(...)):
    raw = {f.filename: await f.read() for f in files}
    return store.load_upload(raw)


@router.get("/analytics")
def analytics():
    return compute_analytics()


@router.get("/recommendations")
def recommendations(lang: str = "en"):
    return ai_recommendations(lang)


@router.get("/products")
def products():
    return product_list()


@router.get("/product-dna/{product_id}")
def dna(product_id: str):
    result = product_dna(product_id)
    return result or {"error": "product not found"}


@router.post("/ceo-report")
def ceo_report(lang: str = "en"):
    return ai_ceo_report(lang)


@router.post("/simulate")
def simulate(payload: dict):
    return ai_simulate(payload)
