"""ProductIQ smoke test — verifies the analytics engine and API wiring offline.
Run from backend/:  python ../tests/smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database.store import store                      # noqa: E402
from app.services.analysis.engine import (                # noqa: E402
    compute_analytics,
    product_dna,
    product_list,
)
from app.services.ai.chains import _fallback_recommendations, _fallback_simulation  # noqa: E402


def main():
    store.load_sample()
    assert store.ready, "store not ready"

    a = compute_analytics()
    assert a["kpis"]["revenue"] > 0, "revenue should be positive"
    assert len(a["top_sellers"]) == 5, "expected 5 top sellers"
    assert len(a["weekly_trend"]) >= 4, "expected weekly trend"
    print(f"  analytics: revenue={a['kpis']['revenue']} EGP, "
          f"margin={a['kpis']['margin']}%, turnover={a['kpis']['turnover']}x")

    products = product_list()
    assert len(products) == 10, "expected 10 products"

    dna = product_dna(products[0]["id"])
    assert dna and len(dna["dimensions"]) == 8, "DNA needs 8 dimensions"
    assert 0 <= dna["health_score"] <= 100, "health score out of range"
    print(f"  DNA {products[0]['name']}: health={dna['health_score']}")

    recs = _fallback_recommendations(a)
    assert recs["recommendations"], "fallback recs empty"
    print(f"  fallback recs: {len(recs['recommendations'])} items")

    sim = _fallback_simulation({"product_name": "Test", "current_price": 5990,
                                "change_type": "price decrease", "change_value": "10"})
    assert sim["demand_change_pct"] > 0, "price cut should raise demand"
    print(f"  fallback sim: demand {sim['demand_change_pct']}%")

    print("All smoke tests passed [OK]")


if __name__ == "__main__":
    main()
