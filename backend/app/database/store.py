"""In-memory data store for ProductIQ.
Holds pandas DataFrames for products, sales, inventory, suppliers.
Data arrives either from the bundled sample CSVs or from user uploads.
"""
import io
from pathlib import Path

import pandas as pd

from app.core.config import DATA_DIR


class Store:
    def __init__(self):
        self.products: pd.DataFrame | None = None
        self.sales: pd.DataFrame | None = None
        self.inventory: pd.DataFrame | None = None
        self.suppliers: pd.DataFrame | None = None
        self.source: str = "none"  # "sample" | "upload" | "none"
        self.validation_report: list[dict] = []

    # ── loading ──────────────────────────────────────────────
    def load_sample(self):
        self.products = pd.read_csv(DATA_DIR / "products.csv")
        self.sales = pd.read_csv(DATA_DIR / "sales.csv", parse_dates=["date"])
        self.inventory = pd.read_csv(DATA_DIR / "inventory.csv")
        self.suppliers = pd.read_csv(DATA_DIR / "suppliers.csv")
        self.source = "sample"
        self.validation_report = []

    def load_upload(self, files: dict[str, bytes]) -> dict:
        """files: {filename: raw_bytes}. Returns per-file validation summary."""
        summary = []
        report = []
        mapping = {
            "products": "products", "sales": "sales",
            "inventory": "inventory", "suppliers": "suppliers",
        }
        for fname, raw in files.items():
            key = next((v for k, v in mapping.items() if k in fname.lower()), None)
            if key is None:
                summary.append({"name": fname, "rows": 0, "valid": 0, "flagged": 0,
                                "rejected": 0, "note": "unrecognized file"})
                continue
            df = pd.read_csv(io.BytesIO(raw))
            rows, rejected = len(df), 0
            # --- basic hard validation ---
            if "price" in " ".join(df.columns).lower():
                price_col = next(c for c in df.columns if "price" in c.lower())
                bad = int((df[price_col] < 0).sum())
                df = df[df[price_col] >= 0]
                rejected += bad
                if bad:
                    report.append({"file": fname, "row": "-",
                                   "reason_en": f"{bad} row(s) with negative price rejected",
                                   "reason_ar": f"تم رفض {bad} صف بسعر سالب"})
            if key == "sales":
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                dupes = int(df.duplicated(subset=["transaction_id"]).sum()) if "transaction_id" in df.columns else 0
                if dupes:
                    report.append({"file": fname, "row": "-",
                                   "reason_en": f"{dupes} duplicate transaction id(s) flagged",
                                   "reason_ar": f"تم تمييز {dupes} معاملة مكررة"})
            setattr(self, key, df)
            summary.append({"name": fname, "rows": rows, "valid": rows - rejected,
                            "flagged": len(report), "rejected": rejected})
        self.source = "upload"
        self.validation_report = report
        return {"ok": True, "sample": False, "files": summary, "flags": report}

    @property
    def ready(self) -> bool:
        return self.products is not None and self.sales is not None

    def ensure_loaded(self):
        if not self.ready:
            self.load_sample()


store = Store()
