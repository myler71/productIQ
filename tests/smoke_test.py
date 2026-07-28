"""ProductIQ smoke test — verifies the analytics engine and API wiring offline.
Run from backend/:  python ../tests/smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database.store import Store, manager
from app.services.analysis.engine import compute_analytics, product_dna, product_list
from app.services.analysis.simulation import simulate_change
from app.services.ai.chains import _fallback_recommendations, _fallback_report
from app.services.ai.crew import run_board_meeting


def main():
    manager._stores.clear()
    store = Store()
    store.load_sample()
    assert store.ready, "store not ready"

    a = compute_analytics(store)
    assert a["kpis"]["revenue"] > 0, "revenue should be positive"
    assert len(a["top_sellers"]) == 5, "expected 5 top sellers"
    assert len(a["weekly_trend"]) >= 4, "expected weekly trend"
    print(f"  analytics: revenue={a['kpis']['revenue']} EGP, "
          f"margin={a['kpis']['margin']}%, turnover={a['kpis']['turnover']}x")

    products = product_list(store)
    assert len(products) == 10, "expected 10 products"

    dna = product_dna(products[0]["id"], store)
    assert dna and len(dna["dimensions"]) == 8, "DNA needs 8 dimensions"
    assert 0 <= dna["health_score"] <= 100, "health score out of range"
    print(f"  DNA {products[0]['name']}: health={dna['health_score']}")

    recs = _fallback_recommendations(a)
    assert recs["recommendations"], "fallback recs empty"
    print(f"  fallback recs: {len(recs['recommendations'])} items")

    sim = simulate_change(
        product_name="Test", category="Smartphones", current_price=5990,
        cost=5100, current_velocity_monthly=45,
        change_type="price decrease", change_value_pct=10
    )
    assert sim["demand_change_pct"] > 0, "price cut should raise demand"
    print(f"  simulation: demand {sim['demand_change_pct']}%")

    board = run_board_meeting("P001", "en", store)
    assert board["engine"] == "deterministic"
    assert len(board["transcript"]) == 4
    print(f"  board meeting: {len(board['transcript'])} agents")

    print("All smoke tests passed [OK]")


if __name__ == "__main__":
    main()
