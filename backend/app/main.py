"""ProductIQ — FastAPI entrypoint.
Run:  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
Then open http://127.0.0.1:8000 (serves the frontend) or use the API directly.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.routes import router
from app.core.config import API_HOST, API_PORT, GROQ_MODEL, PROJECT_ROOT
from app.database.store import manager
from app.database.users import seed_admin
from app.services.ai.llm import llm_status

app = FastAPI(title="ProductIQ", version="4.0.0",
              description="AI Retail Decision Support for the Egyptian market")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(router)


@app.on_event("startup")
def preload():
    """Load the bundled Egyptian sample dataset, seed admin, log startup mode."""
    manager.get("anonymous").load_sample()
    seed_admin()
    status = llm_status()
    if status["available"]:
        print(f"[ProductIQ] Booted in LLM mode: {status['model']}")
    else:
        print(f"[ProductIQ] Booted in DETERMINISTIC mode. Last error: {status['last_error']}")


# Serve the frontend (mounted last so /api wins)
frontend_dir = PROJECT_ROOT / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
