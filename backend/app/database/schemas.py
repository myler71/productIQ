"""CSV schema validation for ProductIQ uploads.
Centralises the expected columns per file, types, and basic hard-rule checks.
"""
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd


@dataclass
class ColumnSpec:
    name: str
    required: bool = True
    dtype: str | None = None
    validator: Callable[[pd.Series], pd.Series] | None = None
    reason: str = "invalid value"


@dataclass
class ValidationResult:
    ok: bool
    rows_total: int
    rows_valid: int
    rows_rejected: int
    valid_mask: Any = field(default_factory=lambda: pd.Series([], dtype=bool))
    flags: list[dict] = field(default_factory=list)
    rejected_reasons: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok

    def valid_indices(self) -> list[int]:
        if len(self.valid_mask) == 0:
            return []
        return [int(i) for i, ok in self.valid_mask.items() if ok]


PRODUCTS_SCHEMA = [
    ColumnSpec("product_id"),
    ColumnSpec("product_name"),
    ColumnSpec("product_name_ar", required=False),
    ColumnSpec("category"),
    ColumnSpec("category_ar", required=False),
    ColumnSpec("brand", required=False),
    ColumnSpec("unit_cost_egp", dtype="float", validator=lambda s: s >= 0, reason="negative cost"),
    ColumnSpec("selling_price_egp", dtype="float", validator=lambda s: s >= 0, reason="negative price"),
    ColumnSpec("supplier_id", required=False),
]

SALES_SCHEMA = [
    ColumnSpec("transaction_id"),
    ColumnSpec("date"),
    ColumnSpec("product_id"),
    ColumnSpec("quantity", dtype="int", validator=lambda s: s > 0, reason="quantity <= 0"),
    ColumnSpec("unit_price_egp", dtype="float", validator=lambda s: s >= 0, reason="negative price"),
    ColumnSpec("discount_egp", required=False, dtype="float", validator=lambda s: s >= 0, reason="negative discount"),
]

INVENTORY_SCHEMA = [
    ColumnSpec("product_id"),
    ColumnSpec("current_stock", dtype="int", validator=lambda s: s >= 0, reason="negative stock"),
    ColumnSpec("reorder_point", required=False, dtype="int", validator=lambda s: s >= 0, reason="negative reorder point"),
    ColumnSpec("last_restock_date", required=False),
]

SUPPLIERS_SCHEMA = [
    ColumnSpec("supplier_id"),
    ColumnSpec("supplier_name"),
    ColumnSpec("supplier_name_ar", required=False),
    ColumnSpec("contact", required=False),
    ColumnSpec("lead_time_days", required=False, dtype="int", validator=lambda s: s >= 0, reason="negative lead time"),
    ColumnSpec("reliability_score", required=False, dtype="int", validator=lambda s: (s >= 0) & (s <= 100), reason="score outside 0-100"),
]

SCHEMAS = {
    "products": PRODUCTS_SCHEMA,
    "sales": SALES_SCHEMA,
    "inventory": INVENTORY_SCHEMA,
    "suppliers": SUPPLIERS_SCHEMA,
}


def validate_dataframe(df: pd.DataFrame, schema: list[ColumnSpec]) -> ValidationResult:
    """Run schema checks. Returns a ValidationResult with rejected rows + flags."""
    flags = []
    rejected_reasons = []
    mask = pd.Series([True] * len(df), index=df.index)

    for col in schema:
        if col.required and col.name not in df.columns:
            rejected_reasons.append(f"missing required column: {col.name}")
            return ValidationResult(ok=False, rows_total=len(df), rows_valid=0,
                                    rows_rejected=len(df), valid_mask=pd.Series([False] * len(df), index=df.index),
                                    flags=[], rejected_reasons=rejected_reasons)
        if col.name not in df.columns:
            continue
        if col.dtype == "float":
            df[col.name] = pd.to_numeric(df[col.name], errors="coerce")
        elif col.dtype == "int":
            df[col.name] = pd.to_numeric(df[col.name], errors="coerce")
        if col.validator is not None:
            try:
                valid = col.validator(df[col.name])
                if isinstance(valid, pd.Series):
                    bad_idx = df.index[~valid]
                else:
                    bad_idx = df.index[~valid] if hasattr(valid, '__iter__') and len(valid) == len(df) else []
                for idx in bad_idx[:10]:
                    flags.append({"row": int(idx), "column": col.name, "reason": col.reason})
                    mask.loc[idx] = False
            except Exception:
                pass

    rows_rejected = int((~mask).sum())
    return ValidationResult(
        ok=True,
        rows_total=len(df),
        rows_valid=len(df) - rows_rejected,
        rows_rejected=rows_rejected,
        valid_mask=mask,
        flags=flags,
        rejected_reasons=rejected_reasons,
    )


def identify_file(filename: str) -> str | None:
    """Map a filename to the internal key (products, sales, inventory, suppliers)."""
    name_lower = filename.lower()
    for key in SCHEMAS:
        if key in name_lower:
            return key
    return None
