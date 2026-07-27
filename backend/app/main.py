"""ProductIQ — FastAPI entrypoint.
Run:  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
Then open http://127.0.0.1:8000 (serves the frontend) or use the API directly.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import PROJECT_ROOT
from app.database.store import store

app = FastAPI(title="ProductIQ", version="1.0.0",
              description="AI Retail Decision Support for the Egyptian market")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only — restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def preload():
    """Load the bundled Egyptian sample dataset on boot so the demo is instant."""
    store.ensure_loaded()


# Serve the frontend (mounted last so /api wins)
frontend_dir = PROJECT_ROOT / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
