"""Tests for AI chains (recommendations, CEO report, simulation)."""
from app.database.store import Store
from app.services.ai.chains import ai_ceo_report, ai_recommendations, ai_simulate


def test_ai_recommendations_has_engine_field(mock_llm_available, reset_stores):
    store = Store()
    store.load_sample()
    result = ai_recommendations("en", store)
    assert "engine" in result
    assert "recommendations" in result


def test_ai_recommendations_fallback_when_offline(mock_llm_offline, reset_stores):
    store = Store()
    store.load_sample()
    result = ai_recommendations("en", store)
    assert result["engine"] == "deterministic"
    assert result["recommendations"]


def test_ai_ceo_report_has_engine_field(mock_llm_available, reset_stores):
    store = Store()
    store.load_sample()
    result = ai_ceo_report("en", store)
    assert "engine" in result
    assert "summary_en" in result


def test_ai_simulate_returns_deterministic_numbers(mock_llm_available, reset_stores):
    store = Store()
    store.load_sample()
    result = ai_simulate({
        "product_id": "P001", "product_name": "Samsung Galaxy A56",
        "current_price": 5990, "change_type": "price decrease", "change_value": 10
    }, store)
    assert "demand_change_pct" in result
    assert "revenue_impact_egp" in result
    assert "profit_impact_egp" in result
    assert "risk_level" in result
    assert "engine" in result
