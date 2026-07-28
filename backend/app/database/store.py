"""Session-scoped atomic data store for ProductIQ.
Each browser/session cookie gets its own Store instance with its own DataFrames.
Logged-in users (Task 2) are isolated by a distinct session key.
"""
import io
import uuid
from pathlib import Path

import pandas as pd
from fastapi import Cookie, Request, Response

from app.core.config import DATA_DIR, SQLITE_DIR
from app.database.schemas import SCHEMAS, identify_file, validate_dataframe


class Store:
    """One dataset per session: products, sales, inventory, suppliers."""

    def __init__(self):
        self.products: pd.DataFrame | None = None
        self.sales: pd.DataFrame | None = None
        self.inventory: pd.DataFrame | None = None
        self.suppliers: pd.DataFrame | None = None
        self.source: str = "none"
        self.validation_report: list[dict] = []
        self._loaded: bool = False

    def load_sample(self) -> None:
        """Load the bundled Egyptian sample dataset."""
        self.products = pd.read_csv(DATA_DIR / "products.csv")
        self.sales = pd.read_csv(DATA_DIR / "sales.csv", parse_dates=["date"])
        self.inventory = pd.read_csv(DATA_DIR / "inventory.csv")
        self.suppliers = pd.read_csv(DATA_DIR / "suppliers.csv")
        self.source = "sample"
        self.validation_report = []
        self._loaded = True

    def load_upload(self, files: dict[str, bytes]) -> dict:
        """files: {filename: raw_bytes}. Returns per-file validation summary."""
        summary = []
        report = []
        for fname, raw in files.items():
            key = identify_file(fname)
            if key is None:
                summary.append({
                    "name": fname, "rows": 0, "valid": 0, "flagged": 0,
                    "rejected": 0, "note": "unrecognized file",
                })
                continue
            df = pd.read_csv(io.BytesIO(raw))
            result = validate_dataframe(df, SCHEMAS[key])
            if not result:
                summary.append({
                    "name": fname, "rows": result.rows_total, "valid": 0,
                    "flagged": 0, "rejected": result.rows_total,
                    "note": result.rejected_reasons[0] if result.rejected_reasons else "schema validation failed",
                })
                continue
            df = df[result.valid_mask].copy()
            if key == "sales":
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                dupes = int(df.duplicated(subset=["transaction_id"]).sum()) if "transaction_id" in df.columns else 0
                if dupes:
                    report.append({"file": fname, "row": "-", "reason": f"{dupes} duplicate transaction ids"})
            setattr(self, key, df)
            summary.append({
                "name": fname, "rows": result.rows_total, "valid": result.rows_valid,
                "flagged": len(result.flags), "rejected": result.rows_rejected,
                "note": "",
            })
            report.extend([{**f, "file": fname} for f in result.flags])
        self.source = "upload"
        self.validation_report = report
        self._loaded = True
        return {"ok": True, "sample": False, "files": summary, "flags": report}

    @property
    def ready(self) -> bool:
        return self.products is not None and self.sales is not None

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load_sample()

    def __repr__(self) -> str:
        return f"<Store source={self.source} loaded={self._loaded}>"


class StoreManager:
    """Holds one Store per session id, lazily initialised with sample data."""

    def __init__(self):
        SQLITE_DIR.mkdir(parents=True, exist_ok=True)
        self._stores: dict[str, Store] = {}

    def get(self, session_id: str) -> Store:
        if session_id not in self._stores:
            self._stores[session_id] = Store()
            self._stores[session_id].load_sample()
        return self._stores[session_id]

    def get_user_store(self, username: str) -> Store:
        """Isolated store for an authenticated user."""
        key = f"user:{username}"
        if key not in self._stores:
            self._stores[key] = Store()
            self._stores[key].load_sample()
        return self._stores[key]


def ensure_session_cookie(request: Request, response: Response) -> str:
    """Return the existing productiq_session cookie, or set a new one."""
    sid = request.cookies.get("productiq_session")
    if not sid:
        sid = str(uuid.uuid4())
        response.set_cookie(
            key="productiq_session",
            value=sid,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
    return sid


manager = StoreManager()
