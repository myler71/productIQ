"""Tests for the session-scoped store and schema validation."""
import pandas as pd
import pytest

from app.database.schemas import (
    PRODUCTS_SCHEMA,
    SALES_SCHEMA,
    ValidationResult,
    validate_dataframe,
)
from app.database.store import Store, manager


def test_store_loads_sample():
    store = Store()
    store.load_sample()
    assert store.ready
    assert len(store.products) == 10
    assert len(store.sales) > 0


def test_store_manager_session_isolation():
    manager._stores.clear()
    s1 = manager.get("session-a")
    s2 = manager.get("session-b")
    assert s1 is not s2


def test_validate_products_ok():
    df = pd.DataFrame({
        "product_id": ["P001"], "product_name": ["Phone"], "category": ["Smartphones"],
        "unit_cost_egp": [100.0], "selling_price_egp": [150.0]
    })
    result = validate_dataframe(df, PRODUCTS_SCHEMA)
    assert result
    assert result.rows_valid == 1
    assert result.rows_rejected == 0


def test_validate_rejects_negative_price():
    df = pd.DataFrame({
        "product_id": ["P001"], "product_name": ["Phone"], "category": ["Smartphones"],
        "unit_cost_egp": [100.0], "selling_price_egp": [-50.0]
    })
    result = validate_dataframe(df, PRODUCTS_SCHEMA)
    assert result.rows_valid == 0
    assert result.rows_rejected == 1


def test_validate_missing_required_column():
    df = pd.DataFrame({"product_id": ["P001"]})
    result = validate_dataframe(df, PRODUCTS_SCHEMA)
    assert not result
    assert result.rows_rejected == 1


def test_store_upload_rejects_bad_row():
    store = Store()
    csv_bad = b"product_id,product_name,category,unit_cost_egp,selling_price_egp\nP001,Phone,Smartphones,100,-50"
    res = store.load_upload({"products.csv": csv_bad})
    assert res["ok"]
    assert res["files"][0]["rejected"] == 1
    assert res["files"][0]["valid"] == 0
