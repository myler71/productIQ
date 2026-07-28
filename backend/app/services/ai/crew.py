"""AI Board Meeting — multi-agent product evaluation.
Uses sequential LangChain LLM calls with distinct personas (CFO, Marketing,
Inventory Manager, CEO) to simulate a board meeting. Each agent analyzes
the product from their angle; the CEO agent reviews all three and makes
the final call.

This is the LangChain implementation of the CrewAI pattern shown in the
notebook — lighter dependencies, same demo result. Falls back to
deterministic output if the LLM is offline.
"""
import json
import re
from datetime import timedelta

from app.services.analysis.engine import compute_analytics, _joined
from app.services.ai.llm import invoke_llm, llm_status
from app.services.memory.store import record_board_decision


def _product_context(product_id: str, store) -> str:
    """Build a text summary of the product for the agents to debate."""
    store.ensure_loaded()
    prod = store.products[store.products["product_id"] == product_id]
    if prod.empty:
        return "Product not found"
    p = prod.iloc[0]
    inv = store.inventory[store.inventory["product_id"] == product_id]
    stock = int(inv.iloc[0]["current_stock"]) if not inv.empty else 0
    reorder = int(inv.iloc[0]["reorder_point"]) if not inv.empty else 0

    df = _joined()
    today = df["date"].max()
    last_30 = df[(df["date"] > today - timedelta(days=30)) &
                 (df["product_id"] == product_id)]
    sold = int(last_30["quantity"].sum())
    revenue = int(last_30["revenue"].sum())
    profit = int(last_30["profit"].sum())
    margin = round(profit / max(revenue, 1) * 100, 1)

    supplier = store.suppliers[store.suppliers["supplier_id"] == p.supplier_id]
    sup_name = supplier.iloc[0]["supplier_name"] if not supplier.empty else "Unknown"
    sup_reliability = int(supplier.iloc[0]["reliability_score"]) if not supplier.empty else 0
    sup_lead = int(supplier.iloc[0]["lead_time_days"]) if not supplier.empty else 0

    # competitor context
    cat_products = store.products[store.products["category"] == p.category]
    competitors = cat_products[cat_products["product_id"] != product_id]
    comp_info = "; ".join(
        f"{r.product_name} at {int(r.selling_price_egp)} EGP"
        for r in competitors.itertuples()
    ) or "No direct competitors in catalog"

    return f"""Product: {p.product_name}
Category: {p.category} | Brand: {p.brand}
Cost: {int(p.unit_cost_egp)} EGP | Price: {int(p.selling_price_egp)} EGP | Margin: {margin}%
Last 30 days: {sold} units sold, {revenue} EGP revenue, {profit} EGP profit
Current stock: {stock} units (reorder point: {reorder})
Supplier: {sup_name} (reliability: {sup_reliability}%, lead time: {sup_lead} days)
Competitors in catalog: {comp_info}"""


def _agent_call(role, persona, task, context, prior_analyses=""):
    """One agent's turn: persona + task + context (+ prior analyses for CEO)."""
    prior_section = ""
    if prior_analyses:
        prior_section = "Other department heads have already weighed in:\n" + prior_analyses

    prompt = f"""You are the {role} at an Egyptian electronics retail company in Cairo.
{persona}

Analyze this product decision:
{context}

Your task: {task}

{prior_section}

Give your assessment in 3-4 sentences. Be specific with numbers (EGP).
End with a clear one-line recommendation starting with RECOMMENDATION:"""

    result = invoke_llm(prompt, fallback=f"[{role} offline] Unable to analyze. RECOMMENDATION: defer to CEO.")
    return result["content"]


def run_board_meeting(product_id: str, lang: str = "en", store=None) -> dict:
    """Run a 4-agent board meeting on a product. Returns the transcript."""
    if store is None:
        from app.database.store import manager as _manager
        store = _manager.get("anonymous")
    context = _product_context(product_id, store)
    status = llm_status()
    ar = lang == "ar"

    prod = store.products[store.products["product_id"] == product_id]
    if prod.empty:
        return {"error": "product not found", "engine": "deterministic"}
    p = prod.iloc[0]
    product_name = p.product_name_ar if (ar and p.product_name_ar) else p.product_name

    personas = {
        "cfo": {
            "role_en": "CFO", "role_ar": "المدير المالي",
            "persona": "You are the finance chief. You care about margins, cash flow, ROI, and capital efficiency. You hate inventory that ties up cash.",
            "task_en": "Assess the financial viability: margin adequacy, capital tied in stock, ROI, overstocking risk.",
            "task_ar": "تقييم الجدوى المالية: كفاية الهامش، رأس المال المحجوز، العائد على الاستثمار، مخاطر الإفراط في المخزون.",
            "color": "#3B82F6",
        },
        "marketing": {
            "role_en": "Marketing Director", "role_ar": "مدير التسويق",
            "persona": "You track Egyptian social media trends, competitor moves, and customer sentiment. You know what sells in Cairo.",
            "task_en": "Assess market demand, brand pull, competitor positioning, and customer sentiment in Egypt.",
            "task_ar": "تقييم طلب السوق، قوة العلامة، positioning المنافسين، ومشاعر العملاء في مصر.",
            "color": "#10B981",
        },
        "inventory": {
            "role_en": "Inventory Manager", "role_ar": "مدير المخزون",
            "persona": "You manage the Cairo warehouse. You know turnover, supplier reliability, storage limits. You hate dead stock.",
            "task_en": "Assess stock health: turnover, days-of-stock, supplier reliability, reorder urgency.",
            "task_ar": "تقييم صحة المخزون: الدوران، أيام المخزون، موثوقية المورد، إلحاح إعادة الطلب.",
            "color": "#F59E0B",
        },
        "ceo": {
            "role_en": "CEO", "role_ar": "الرئيس التنفيذي",
            "persona": "You are the CEO. You balance growth, risk, and cash. You make the final call after hearing all departments.",
            "task_en": "Review all three assessments and make the FINAL DECISION: stock or not, how many units, and why.",
            "task_ar": "راجع التقييمات الثلاثة واتخذ القرار النهائي: تخزين أم لا، كم وحدة، ولماذا.",
            "color": "#0B1F3A",
        },
    }

    if status["available"]:
        # Sequential agent calls
        cfo_text = _agent_call("CFO", personas["cfo"]["persona"], personas["cfo"]["task_en"], context)
        mkt_text = _agent_call("Marketing Director", personas["marketing"]["persona"], personas["marketing"]["task_en"], context)
        inv_text = _agent_call("Inventory Manager", personas["inventory"]["persona"], personas["inventory"]["task_en"], context)
        prior = f"CFO: {cfo_text}\n\nMarketing: {mkt_text}\n\nInventory: {inv_text}"
        ceo_text = _agent_call("CEO", personas["ceo"]["persona"], personas["ceo"]["task_en"], context, prior)
        engine = "llm"
    else:
        # Deterministic fallback
        a = compute_analytics()
        cfo_text = _fallback_agent("cfo", context, a)
        mkt_text = _fallback_agent("marketing", context, a)
        inv_text = _fallback_agent("inventory", context, a)
        ceo_text = _fallback_agent("ceo", context, a)
        engine = "deterministic"

    transcript_data = [
        {"role_en": personas["cfo"]["role_en"], "role_ar": personas["cfo"]["role_ar"],
         "color": personas["cfo"]["color"], "analysis": cfo_text},
        {"role_en": personas["marketing"]["role_en"], "role_ar": personas["marketing"]["role_ar"],
         "color": personas["marketing"]["color"], "analysis": mkt_text},
        {"role_en": personas["inventory"]["role_en"], "role_ar": personas["inventory"]["role_ar"],
         "color": personas["inventory"]["color"], "analysis": inv_text},
        {"role_en": personas["ceo"]["role_en"], "role_ar": personas["ceo"]["role_ar"],
         "color": personas["ceo"]["color"], "analysis": ceo_text, "is_final": True},
    ]
    verdict = transcript_data[-1]["analysis"] if transcript_data else ""
    record_board_decision(product_name, context, transcript_data, verdict, engine)
    return {
        "product_name": product_name,
        "context": context,
        "engine": engine,
        "transcript": transcript_data,
    }


def _fallback_agent(role, context, analytics):
    """Rule-based fallback when LLM is offline."""
    if "margin" in context.lower():
        import re as _re
        m = _re.search(r"Margin: ([\d.]+)%", context)
        margin = float(m.group(1)) if m else 15
    else:
        margin = 15

    if role == "cfo":
        verdict = "adequate" if margin >= 15 else "thin"
        return f"Margin is {margin}% — {verdict} for this category. Capital efficiency depends on turnover. RECOMMENDATION: {'proceed if turnover is healthy' if margin >= 15 else 'negotiate better cost before restocking'}."
    elif role == "marketing":
        return "Mid-range smartphones have strong demand in the Egyptian market, especially among students and young professionals. Competitor pricing is a factor. RECOMMENDATION: stock if competitively priced."
    elif role == "inventory":
        return "Stock levels and supplier reliability determine restock urgency. Dead stock ties capital. RECOMMENDATION: reorder only if sell-through rate justifies it."
    else:  # ceo
        return f"Based on department inputs, the product has a {margin}% margin. Balance the financial, market, and inventory considerations. RECOMMENDATION: stock conservatively (30-50 units) and reassess after one month."
