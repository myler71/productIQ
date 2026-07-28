"""Tests for the deterministic analytics engine."""
from app.database.store import Store, manager
from app.services.analysis.engine import compute_analytics, product_dna, product_list


def test_compute_analytics_keys():
    manager._stores.clear()
    store = Store()
    store.load_sample()
    a = compute_analytics(store)
    assert "kpis" in a
    assert "top_sellers" in a
    assert "category_revenue" in a
    assert "weekly_trend" in a
    assert "slow_movers" in a
    assert "stock_risk" in a


def test_compute_analytics_kpis_positive():
    store = Store()
    store.load_sample()
    a = compute_analytics(store)
    assert a["kpis"]["revenue"] > 0
    assert a["kpis"]["profit"] > 0


def test_product_list_returns_ten():
    store = Store()
    store.load_sample()
    products = product_list(store)
    assert len(products) == 10
    assert all("id" in p and "name" in p for p in products)


def test_product_dna_known_product():
    store = Store()
    store.load_sample()
    dna = product_dna("P001", store)
    assert dna is not None
    assert "dimensions" in dna
    assert len(dna["dimensions"]) == 8
    assert 0 <= dna["health_score"] <= 100


def test_product_dna_missing_product():
    store = Store()
    store.load_sample()
    assert product_dna("NOT_REAL", store) is None
