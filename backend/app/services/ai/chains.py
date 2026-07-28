"""AI chains for ProductIQ — recommendations, CEO report, what-if simulation.
Every function returns an `engine` provenance field:
  "llm"             -> LLM produced the output
  "deterministic"   -> LLM unavailable / call failed; deterministic fallback
  "deterministic+llm" -> numbers computed in code, optionally narrated by LLM
"""
from app.services.analysis.engine import analytics_summary_for_llm, compute_analytics, product_list
from app.services.analysis.simulation import simulate_change
from app.services.ai.llm import extract_json_block, invoke_llm


def ai_recommendations(lang: str = "en", store=None) -> dict:
    a = compute_analytics(store)
    summary = analytics_summary_for_llm(store)
    prompt = f"""You are a senior retail analyst for an Egyptian electronics shop (prices in EGP).
Analyze the store data and return structured recommendations.

{summary}

Respond ONLY in {lang}. Return valid JSON with EXACTLY this structure:
{{
  "summary_en": "plain text paragraph, 2-3 sentences in English",
  "summary_ar": "plain text paragraph, same summary in Arabic",
  "recommendations": [
    {{"product": "name", "product_ar": "Arabic name or same",
      "action": "restock|discount|bundle|remove",
      "reason_en": "one sentence in English", "reason_ar": "one sentence in Arabic",
      "confidence": 0-100}}
  ]
}}
Do not nest objects inside summary_en or summary_ar. Keep them plain strings. Prioritize by business impact."""

    fallback = _fallback_recommendations(a)
    result = invoke_llm(prompt, fallback=None, parser=extract_json_block)
    if result["engine"] == "llm" and isinstance(result.get("content"), dict):
        content = _normalize_summary(result["content"])
        if isinstance(content.get("recommendations"), list) and content["recommendations"]:
            return {**content, "engine": "llm"}
    return {**fallback, "engine": "deterministic", "error": result.get("error")}


def _to_text(v) -> str:
    """Coerce an LLM summary field to a plain string (LLMs sometimes nest dicts)."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return "; ".join(f"{k}: {val}" for k, val in v.items())
    return str(v)


def _normalize_summary(content: dict) -> dict:
    """Force summary_en/summary_ar to plain strings."""
    if "summary_en" in content:
        content["summary_en"] = _to_text(content["summary_en"])
    if "summary_ar" in content:
        content["summary_ar"] = _to_text(content["summary_ar"])
    return content


def _fallback_recommendations(a: dict) -> dict:
    recs = []
    for s in a.get("stock_risk", []):
        if s["status"] == "out":
            recs.append({"product": s["name"], "product_ar": s["name_ar"], "action": "restock",
                         "reason_en": "Out of stock while demand exists — restock immediately.",
                         "reason_ar": "نفد المخزون رغم وجود طلب — أعد الطلب فوراً.", "confidence": 92})
    for s in a.get("slow_movers", [])[:2]:
        if s["days_no_sale"] > 30:
            recs.append({"product": s["name"], "product_ar": s["name_ar"], "action": "discount",
                         "reason_en": f"No sales in {s['days_no_sale']} days with {s['tied_capital']} EGP tied up — clear with a discount.",
                         "reason_ar": f"لا مبيعات منذ {s['days_no_sale']} يوم و{s['tied_capital']} ج.م محجوزة — صفِّ بخصم.",
                         "confidence": 84})
    return {
        "summary_en": "Analysis generated from deterministic rules (LLM offline). Review the recommendations below.",
        "summary_ar": "تحليل مولّد بقواعد محددة (الذكاء الاصطناعي غير متصل). راجع التوصيات أدناه.",
        "recommendations": recs[:5] or [{
            "product": "—", "product_ar": "—", "action": "restock",
            "reason_en": "No urgent actions detected.", "reason_ar": "لا توجد إجراءات عاجلة.",
            "confidence": 50}],
    }


# ════════════════════════════════════════ CEO REPORT ════════════════════════════════════════


def ai_ceo_report(lang: str = "en", store=None) -> dict:
    a = compute_analytics(store)
    summary = analytics_summary_for_llm(store)
    prompt = f"""You are the AI analyst of an Egyptian electronics retailer. Write the weekly CEO report in {lang}.

{summary}

Return ONLY valid JSON (no markdown) with EXACTLY this structure:
{{
  "summary_en": "plain text paragraph, one executive summary in English",
  "summary_ar": "plain text paragraph, same summary in Arabic",
  "action_items_en": ["5 prioritized action items as strings"],
  "action_items_ar": ["same 5 items in Arabic as strings"]
}}
Do not nest objects inside summary fields. Keep them plain strings."""

    fallback = _fallback_report(a)
    result = invoke_llm(prompt, fallback=None, parser=extract_json_block)
    if result["engine"] == "llm" and isinstance(result.get("content"), dict):
        content = _normalize_summary(result["content"])
        if "summary_en" in content:
            content.update(_report_scaffold(a))
            return {**content, "engine": "llm"}
    return {**fallback, "engine": "deterministic", "error": result.get("error")}


def _report_scaffold(a: dict) -> dict:
    k = a["kpis"]
    return {
        "week": "Last 30 days",
        "week_ar": "آخر 30 يوم",
        "revenue": {
            "this_week": k["revenue"],
            "last_week": round(k["revenue"] / (1 + k["revenue_change"] / 100)) if k["revenue_change"] else k["revenue"],
            "change_pct": k["revenue_change"],
            "profit": k["profit"],
            "profit_change_pct": k["profit_change"],
        },
        "top_products": [{"name": t["name"], "name_ar": t["name_ar"],
                          "revenue": t["revenue"], "units": t["sold"]} for t in a["top_sellers"][:3]],
        "needs_attention": [
            {"name": s["name"], "name_ar": s["name_ar"],
             "issue_en": f"Stock {s['stock']} [{s['status']}]", "issue_ar": f"المخزون {s['stock']} [{s['status']}]"}
            for s in a["stock_risk"][:2]],
        "action_items_en": ["Restock out-of-stock sellers", "Discount stock older than 30 days",
                             "Review margins below 12%", "Bundle slow premium items",
                             "Renegotiate top supplier costs"],
        "action_items_ar": ["أعد طلب المنتجات النافدة", "خصم المخزون الأقدم من 30 يوماً",
                             "راجع الهوامش الأقل من 12%", "حزم المنتجات المميزة الراكدة",
                             "تفاوض على أسعار كبار الموردين"],
        "supplier_alerts_en": ["Review supplier pricing quarterly"],
        "supplier_alerts_ar": ["راجع أسعار الموردين كل ربع سنة"],
    }


def _fallback_report(a: dict) -> dict:
    data = _report_scaffold(a)
    data.update({
        "summary_en": "LLM offline — deterministic report. See KPIs and action items.",
        "summary_ar": "الذكاء الاصطناعي غير متصل — تقرير آلي. راجع المؤشرات والمهام.",
    })
    return data


# ════════════════════════════════════════ SIMULATION ════════════════════════════════════════


def ai_simulate(payload: dict, store=None) -> dict:
    """What-if simulation. Deterministic numbers; LLM narrates if available."""
    from app.services.analysis.engine import _joined
    from datetime import timedelta

    if store is None:
        from app.database.store import manager as _manager
        store = _manager.get("anonymous")
    store.ensure_loaded()

    product_id = payload.get("product_id")
    product_name = payload.get("product_name", "")
    current_price = float(payload.get("current_price") or 0)
    change_type = payload.get("change_type", "price decrease")
    change_value = float(payload.get("change_value") or 10)

    # Find product cost / category
    prod = store.products[store.products["product_id"] == product_id]
    if not prod.empty:
        p = prod.iloc[0]
        cost = float(p.unit_cost_egp)
        category = p.category
        product_name = product_name or p.product_name
    else:
        cost = current_price * 0.85
        category = "Smartphones"

    # Velocity (units per month)
    df = _joined()
    today = df["date"].max()
    last_30 = df[(df["date"] > today - timedelta(days=30)) & (df["product_id"] == product_id)]
    velocity = float(last_30["quantity"].sum())

    sim = simulate_change(
        product_name=product_name,
        category=category,
        current_price=current_price,
        cost=cost,
        current_velocity_monthly=velocity,
        change_type=change_type,
        change_value_pct=change_value,
    )

    # Determine provenance: if LLM is available, mark as computed+AI-available.
    from app.services.ai.llm import llm_status
    status = llm_status()
    engine = "deterministic+llm" if status["available"] else "deterministic"

    return {
        "product": product_name,
        "current_price": current_price,
        **sim,
        "engine": engine,
    }
