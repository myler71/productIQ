"""AI chains for ProductIQ — recommendations, CEO report, what-if simulation.
Each function: try the LLM with structured JSON output; on any failure,
fall back to deterministic rule-based output derived from the analytics.
"""
import json
import re

from app.services.analysis.engine import (
    analytics_summary_for_llm,
    compute_analytics,
    product_list,
)
from app.services.ai.llm import get_llm


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of an LLM response."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ═══════════════ 1. RECOMMENDATIONS ═══════════════

def ai_recommendations(lang: str = "en") -> dict:
    a = compute_analytics()
    llm = get_llm()
    if llm:
        try:
            prompt = f"""You are a senior retail analyst for an Egyptian electronics shop (prices in EGP).
Here is the store's analytics summary:

{analytics_summary_for_llm()}

Return ONLY valid JSON (no markdown) with this exact shape:
{{
  "summary_en": "2-3 sentence executive summary in English",
  "summary_ar": "same summary in Arabic",
  "recommendations": [
    {{"product": "name", "product_ar": "Arabic name if known, else same",
      "action": "restock|discount|bundle|remove",
      "reason_en": "one sentence", "reason_ar": "one sentence in Arabic",
      "confidence": 0-100}}
  ]
}}
Give 3-5 recommendations, prioritized by business impact."""
            resp = llm.invoke(prompt)
            data = _extract_json(resp.content)
            if data and "recommendations" in data:
                return data
        except Exception:
            pass
    return _fallback_recommendations(a)


def _fallback_recommendations(a: dict) -> dict:
    recs = []
    for s in a["stock_risk"]:
        if s["status"] == "out":
            recs.append({"product": s["name"], "product_ar": s["name_ar"], "action": "restock",
                         "reason_en": "Out of stock while demand exists — restock immediately.",
                         "reason_ar": "نفد المخزون رغم وجود طلب — أعد الطلب فوراً.", "confidence": 92})
    for s in a["slow_movers"][:2]:
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


# ═══════════════ 2. CEO REPORT ═══════════════

def ai_ceo_report(lang: str = "en") -> dict:
    a = compute_analytics()
    k = a["kpis"]
    llm = get_llm()
    if llm:
        try:
            prompt = f"""You are the AI analyst of an Egyptian electronics retailer. Write the weekly CEO report.
Analytics:

{analytics_summary_for_llm()}

Return ONLY valid JSON (no markdown):
{{
  "summary_en": "one paragraph executive summary",
  "summary_ar": "same in Arabic",
  "action_items_en": ["5 prioritized action items"],
  "action_items_ar": ["same 5 items in Arabic"]
}}"""
            resp = llm.invoke(prompt)
            data = _extract_json(resp.content)
            if data and "summary_en" in data:
                data.update(_report_scaffold(a))
                return data
        except Exception:
            pass
    data = _fallback_report(a)
    return data


def _report_scaffold(a: dict) -> dict:
    k = a["kpis"]
    return {
        "week": "Last 30 days",
        "week_ar": "آخر 30 يوم",
        "revenue": {
            "this_week": k["revenue"], "last_week": round(k["revenue"] / (1 + k["revenue_change"] / 100)),
            "change_pct": k["revenue_change"], "profit": k["profit"],
            "profit_change_pct": k["profit_change"],
        },
        "top_products": [{"name": t["name"], "name_ar": t["name_ar"],
                          "revenue": t["revenue"], "units": t["sold"]} for t in a["top_sellers"][:3]],
        "needs_attention": [
            {"name": s["name"], "name_ar": s["name_ar"],
             "issue_en": f"Stock {s['stock']} [{s['status']}]", "issue_ar": f"المخزون {s['stock']} [{s['status']}]"}
            for s in a["stock_risk"][:2]],
        "supplier_alerts_en": ["Review supplier pricing quarterly"],
        "supplier_alerts_ar": ["راجع أسعار الموردين كل ربع سنة"],
    }


def _fallback_report(a: dict) -> dict:
    data = _report_scaffold(a)
    data.update({
        "summary_en": "LLM offline — deterministic report. See KPIs and action items.",
        "summary_ar": "الذكاء الاصطناعي غير متصل — تقرير آلي. راجع المؤشرات والمهام.",
        "action_items_en": ["Restock out-of-stock sellers", "Discount stock older than 30 days",
                             "Review margins below 12%", "Bundle slow premium items",
                             "Renegotiate top supplier costs"],
        "action_items_ar": ["أعد طلب المنتجات النافدة", "خصم المخزون الأقدم من 30 يوماً",
                             "راجع الهوامش الأقل من 12%", "حزم المنتجات المميزة الراكدة",
                             "تفاوض على أسعار كبار الموردين"],
    })
    return data


# ═══════════════ 3. WHAT-IF SIMULATION ═══════════════

def ai_simulate(payload: dict) -> dict:
    llm = get_llm()
    if llm:
        try:
            prompt = f"""You are a retail decision simulator for the Egyptian market (Cairo electronics shop).
Product: {payload.get('product_name')}
Current price: {payload.get('current_price')} EGP
Proposed change: {payload.get('change_type')} by {payload.get('change_value')}%

Estimate the monthly impact realistically. Return ONLY valid JSON (no markdown):
{{
  "demand_change_pct": number,
  "revenue_impact_egp": number,
  "profit_impact_egp": number,
  "risk_level": "low|medium|high",
  "confidence_pct": 0-100,
  "assumptions_en": ["assumption 1", "assumption 2", "assumption 3"],
  "assumptions_ar": ["same in Arabic"]
}}"""
            resp = llm.invoke(prompt)
            data = _extract_json(resp.content)
            if data and "demand_change_pct" in data:
                data["product"] = payload.get("product_name")
                data["current_price"] = payload.get("current_price")
                return data
        except Exception:
            pass
    return _fallback_simulation(payload)


def _fallback_simulation(payload: dict) -> dict:
    change = (payload.get("change_type") or "").lower()
    v = float(payload.get("change_value") or 10)
    price = float(payload.get("current_price") or 0)
    decrease = "decrease" in change or "discount" in change
    elasticity = 2.0
    demand = round(v * elasticity) if decrease else -round(v * 1.5)
    monthly_units = 45
    revenue = round((demand / 100) * monthly_units * price - (v / 100 * price * monthly_units if decrease else 0))
    profit = round(-v / 100 * price * 0.15 * monthly_units) if decrease else round(v / 100 * price * 0.6 * monthly_units)
    return {
        "product": payload.get("product_name"), "current_price": price,
        "demand_change_pct": demand, "revenue_impact_egp": revenue,
        "profit_impact_egp": profit,
        "risk_level": "high" if v > 15 else "medium" if v > 7 else "low",
        "confidence_pct": 65,
        "assumptions_en": [f"Elasticity ≈ {elasticity} (rule-based estimate)",
                            "Competitor prices stable", "No seasonal event in window"],
        "assumptions_ar": [f"مرونة ≈ {elasticity} (تقدير آلي)",
                            "أسعار المنافسين ثابتة", "لا موسم خلال الفترة"],
    }
