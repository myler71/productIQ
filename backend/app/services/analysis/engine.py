"""Deterministic analytics engine — the code does the math, never the LLM.
Computes KPIs, top sellers, trends, slow movers, stock risk and Product DNA scores
from a session-scoped store's DataFrames.
"""
from datetime import timedelta

import numpy as np
import pandas as pd


_DEFAULT_SESSION = "anonymous"


def _store(store=None):
    """Return the passed store or the default anonymous demo store."""
    if store is None:
        from app.database.store import manager
        store = manager.get(_DEFAULT_SESSION)
    store.ensure_loaded()
    return store


def _joined(store=None) -> pd.DataFrame:
    """Sales joined with product cost/price info."""
    store = _store(store)
    wanted = ["product_id", "product_name", "product_name_ar",
              "category", "category_ar", "unit_cost_egp"]
    cols = [c for c in wanted if c in store.products.columns]
    df = store.sales.merge(store.products[cols], on="product_id", how="left")
    df["revenue"] = df["quantity"] * df["unit_price_egp"] - df.get("discount_egp", 0)
    df["cost"] = df["quantity"] * df["unit_cost_egp"]
    df["profit"] = df["revenue"] - df["cost"]
    return df


def _slow_mover_suggestion(margin_pct: float, days_no_sale: int, stock: int) -> str:
    if days_no_sale >= 60 or (days_no_sale >= 30 and margin_pct < 15):
        return "Liquidate — discount 20-30% or bundle to clear"
    if days_no_sale >= 30:
        return "Run a 10-15% discount campaign for 2 weeks; reassess"
    if stock > 10 and margin_pct > 25:
        return "Bundle with a fast-moving product to move stock"
    return "Monitor for 2 more weeks; consider small discount if no change"

def compute_analytics(store=None) -> dict:
    store = _store(store)
    df = _joined(store)
    today = df["date"].max()
    last_30 = df[df["date"] > today - timedelta(days=30)]
    prev_30 = df[(df["date"] <= today - timedelta(days=30)) &
                 (df["date"] > today - timedelta(days=60))]

    revenue = float(last_30["revenue"].sum())
    profit = float(last_30["profit"].sum())
    prev_rev = float(prev_30["revenue"].sum()) or 1.0
    prev_prof = float(prev_30["profit"].sum()) or 1.0

    days = max((today - df["date"].min()).days, 1)
    cogs = float(df["cost"].sum())
    avg_inv_value = float((store.inventory["current_stock"] *
                           store.inventory.merge(store.products, on="product_id")["unit_cost_egp"]).sum())
    turnover = round(cogs / max(avg_inv_value, 1) * (365 / days), 1)

    kpis = {
        "revenue": round(revenue),
        "revenue_change": round((revenue - prev_rev) / prev_rev * 100, 1),
        "profit": round(profit),
        "profit_change": round((profit - prev_prof) / prev_prof * 100, 1),
        "margin": round(profit / max(revenue, 1) * 100, 1),
        "margin_change": 0.0,
        "turnover": turnover,
        "turnover_change": 0.0,
    }

    # top sellers (last 30 days)
    top = (last_30.groupby(["product_id", "product_name", "product_name_ar"])
           .agg(sold=("quantity", "sum"), revenue=("revenue", "sum"),
                profit=("profit", "sum"))
           .reset_index().sort_values("revenue", ascending=False).head(5))
    top_sellers = [{
        "name": r.product_name, "name_ar": r.product_name_ar,
        "sold": int(r.sold), "revenue": round(float(r.revenue)),
        "margin": round(float(r.profit) / max(float(r.revenue), 1) * 100)
    } for r in top.itertuples()]

    # revenue by category
    cat = last_30.groupby(["category", "category_ar"])["revenue"].sum().reset_index()
    category_revenue = [{"category": r.category, "category_ar": r.category_ar,
                         "revenue": round(float(r.revenue))} for r in cat.itertuples()]

    # weekly trend (last 8 weeks)
    trend = df.copy()
    trend["week"] = trend["date"].dt.to_period("W").astype(str)
    wk = trend.groupby("week")["revenue"].sum().reset_index().tail(8)
    weekly_trend = [{"week": r.week, "revenue": round(float(r.revenue))} for r in wk.itertuples()]

    # slow movers — no sales in 30+ days (or lowest velocity), with capital tied
    last_sale = df.groupby("product_id")["date"].max()
    inv = store.inventory.merge(store.products, on="product_id")
    total_days = max(1, (today - df["date"].min()).days)
    # per-product profit over full history
    prod_profit = df.groupby("product_id").agg(
        total_profit=("profit", "sum")
    )
    slow = []
    for r in inv.itertuples():
        ls = last_sale.get(r.product_id)
        days_no_sale = (today - ls).days if ls is not None else days
        if days_no_sale >= 14:
            pp = prod_profit.loc[r.product_id, "total_profit"] if r.product_id in prod_profit.index else 0.0
            avg_monthly_profit = abs(pp) / (total_days / 30.0) if total_days else 0.0
            lost_profit = round((days_no_sale / 30.0) * avg_monthly_profit)
            margin_pct = ((r.selling_price_egp - r.unit_cost_egp) / max(r.selling_price_egp, 1)) * 100
            recovery = _slow_mover_suggestion(margin_pct, days_no_sale, r.current_stock)
            slow.append({
                "name": r.product_name, "name_ar": r.product_name_ar,
                "days_no_sale": int(days_no_sale), "stock": int(r.current_stock),
                "tied_capital": round(float(r.current_stock * r.unit_cost_egp)),
                "lost_profit_egp": lost_profit,
                "recovery_suggestion": recovery,
            })
    slow_movers = sorted(slow, key=lambda x: -x["tied_capital"])[:5]

    # stock risk — below reorder point
    stock_risk = []
    for r in inv.itertuples():
        if r.current_stock == 0:
            status = "out"
        elif r.current_stock <= r.reorder_point:
            status = "critical"
        else:
            continue
        stock_risk.append({"name": r.product_name, "name_ar": r.product_name_ar,
                           "stock": int(r.current_stock), "status": status})

    return {
        "kpis": kpis,
        "top_sellers": top_sellers,
        "category_revenue": category_revenue,
        "weekly_trend": weekly_trend,
        "slow_movers": slow_movers,
        "stock_risk": stock_risk,
    }


def product_list(store=None) -> list[dict]:
    store = _store(store)
    return [{
        "id": r.product_id, "name": r.product_name,
        "name_ar": getattr(r, "product_name_ar", r.product_name),
        "category": r.category,
        "category_ar": getattr(r, "category_ar", r.category),
        "price": float(r.selling_price_egp),
    } for r in store.products.itertuples()]


def product_dna(product_id: str, store=None) -> dict | None:
    """8-dimension fingerprint, all scores 0-100, computed deterministically."""
    store = _store(store)
    df = _joined(store)
    today = df["date"].max()
    last_30 = df[df["date"] > today - timedelta(days=30)]
    prev_30 = df[(df["date"] <= today - timedelta(days=30)) &
                 (df["date"] > today - timedelta(days=60))]

    prod = store.products[store.products["product_id"] == product_id]
    if prod.empty:
        return None
    p = prod.iloc[0]
    inv = store.inventory[store.inventory["product_id"] == product_id]
    stock = int(inv.iloc[0]["current_stock"]) if not inv.empty else 0

    p30 = last_30[last_30["product_id"] == product_id]
    pprev = prev_30[prev_30["product_id"] == product_id]

    sold30 = float(p30["quantity"].sum())
    sold_prev = float(pprev["quantity"].sum())
    rev30 = float(p30["revenue"].sum())
    max_sold = max(float(last_30.groupby("product_id")["quantity"].sum().max()), 1)
    max_rev = max(float(last_30.groupby("product_id")["revenue"].sum().max()), 1)

    margin_pct = (p.selling_price_egp - p.unit_cost_egp) / max(p.selling_price_egp, 1) * 100
    cat_median = float(store.products[store.products["category"] == p.category]
                       ["selling_price_egp"].median())
    price_position = p.selling_price_egp / max(cat_median, 1)  # <1 cheaper than peers

    velocity = sold30 / 30.0
    days_of_stock = stock / velocity if velocity > 0 else 999
    turnover_score = min(100, velocity / (max_sold / 30.0) * 100)
    growth = ((sold30 - sold_prev) / max(sold_prev, 1)) * 100

    dims = {
        "popularity": round(min(100, sold30 / max_sold * 100)),
        "margin": round(min(100, margin_pct / 35 * 100)),
        "demand": round(min(100, rev30 / max_rev * 100)),
        "risk": round(min(100, max(0, 100 - days_of_stock / 90 * 100)) if sold30 > 0 else 20),
        "competitiveness": round(min(100, max(0, (2 - price_position) * 50))),
        "turnover": round(turnover_score),
        "growth": round(min(100, max(0, 50 + growth))),
        "value": round(min(100, (margin_pct * rev30 / max_rev) * 4 + turnover_score * 0.3)),
    }
    dims = {k: int(min(100, max(0, v))) for k, v in dims.items()}
    health = int(np.mean(list(dims.values())))

    return {
        "product": {
            "id": p.product_id, "name": p.product_name, "name_ar": p.product_name_ar,
            "category": p.category, "category_ar": p.category_ar,
            "price": float(p.selling_price_egp),
        },
        "dimensions": dims,
        "health_score": health,
    }


def analytics_summary_for_llm(store=None) -> str:
    """Compact text summary of the analytics — the grounding context for LLM calls."""
    a = compute_analytics(store)
    lines = [
        f"Revenue (30d): {a['kpis']['revenue']} EGP ({a['kpis']['revenue_change']}% vs prior)",
        f"Profit (30d): {a['kpis']['profit']} EGP, Margin: {a['kpis']['margin']}%",
        f"Inventory turnover: {a['kpis']['turnover']}x/year",
        "Top sellers: " + "; ".join(f"{t['name']} ({t['sold']}u, {t['revenue']} EGP)"
                                    for t in a["top_sellers"]),
        "Slow movers: " + ("; ".join(f"{s['name']} ({s['days_no_sale']}d no sale, "
                                     f"{s['tied_capital']} EGP tied)" for s in a["slow_movers"]) or "none"),
        "Stock risk: " + ("; ".join(f"{s['name']} stock={s['stock']} [{s['status']}]"
                                    for s in a["stock_risk"]) or "none"),
    ]
    return "\n".join(lines)
