"""Deterministic pricing / demand simulation model.
Honest, assumption-based what-if calculations: the code does the math, not the LLM.
"""
import math
from typing import TypedDict


class SimulationResult(TypedDict, total=False):
    demand_change_pct: float
    revenue_impact_egp: float
    profit_impact_egp: float
    current_margin_pct: float
    projected_margin_pct: float
    breakeven_units: int
    profit_breakdown: dict
    risk_level: str
    confidence_pct: int
    assumptions_en: list[str]
    assumptions_ar: list[str]


def elasticity_for(category: str, change_type: str) -> float:
    """Return a category-level price elasticity estimate."""
    base = {
        "smartphones": 2.0,
        "audio": 1.4,
        "tablets": 1.6,
        "accessories": 2.4,
        "wearables": 1.3,
        "printers": 0.8,
        "cameras": 0.9,
    }
    cat = (category or "").lower().replace("s", "")  # simple normalisation
    e = base.get(cat, 1.5)
    if "price increase" in change_type or "increase" in change_type:
        return e  # demand moves opposite to price change
    if "discount" in change_type or "bundle" in change_type:
        return e * 1.2
    return e


def simulate_change(
    product_name: str,
    category: str,
    current_price: float,
    cost: float,
    current_velocity_monthly: float,
    change_type: str,
    change_value_pct: float,
) -> SimulationResult:
    """Compute a deterministic what-if estimate.

    Args:
        change_type: e.g. 'price decrease', 'price increase', 'discount campaign', 'bundle'.
        change_value_pct: absolute percentage (e.g. 10 for 10%).
    """
    v = abs(change_value_pct)
    e = elasticity_for(category, change_type)
    decrease = "decrease" in change_type or "discount" in change_type or "bundle" in change_type

    # demand change direction: price cut raises demand; price hike lowers it
    if decrease:
        demand_change = round(v * e, 1)
    else:
        demand_change = -round(v * e * 0.75, 1)

    new_price = current_price
    if "decrease" in change_type:
        new_price = current_price * (1 - v / 100)
    elif "increase" in change_type:
        new_price = current_price * (1 + v / 100)
    elif "discount" in change_type:
        new_price = current_price * (1 - v / 100)
    # bundle leaves price unchanged

    current_monthly_revenue = current_velocity_monthly * current_price
    new_monthly_revenue = current_velocity_monthly * (1 + demand_change / 100) * new_price
    revenue_impact = round(new_monthly_revenue - current_monthly_revenue)

    current_margin = current_price - cost
    new_margin = new_price - cost
    current_profit = current_velocity_monthly * current_margin
    new_profit = current_velocity_monthly * (1 + demand_change / 100) * new_margin
    profit_impact = round(new_profit - current_profit)

    current_margin_pct = round((current_margin / max(current_price, 1)) * 100, 1)
    projected_margin_pct = round((new_margin / max(new_price, 1)) * 100, 1)

    # breakeven: units per month needed at new price to match current profit
    if new_margin > 0 and decrease:
        breakeven_units = max(0, math.ceil(current_profit / new_margin))
    else:
        breakeven_units = max(0, math.ceil(current_profit / max(new_margin, 1)))

    # profit decomposition: volume effect vs margin effect
    volume_impact = round((demand_change / 100) * current_velocity_monthly * current_margin)
    margin_impact = round(current_velocity_monthly * (new_margin - current_margin))

    risk_level = "high" if v > 15 else "medium" if v > 7 else "low"
    confidence_pct = 65 if v > 15 else 75 if v > 7 else 85

    return SimulationResult(
        demand_change_pct=demand_change,
        revenue_impact_egp=revenue_impact,
        profit_impact_egp=profit_impact,
        current_margin_pct=current_margin_pct,
        projected_margin_pct=projected_margin_pct,
        breakeven_units=breakeven_units,
        profit_breakdown={"volume_impact_egp": volume_impact, "margin_impact_egp": margin_impact},
        risk_level=risk_level,
        confidence_pct=confidence_pct,
        assumptions_en=[
            f"Price elasticity estimate for {category}: {e}",
            "Competitor prices assumed stable during the period",
            "No seasonal event (e.g. Ramadan / back-to-school) within the window",
        ],
        assumptions_ar=[
            f"تقدير مرونة السعر لفئة {category}: {e}",
            "أسعار المنافسين مفترضة ثابتة خلال الفترة",
            "لا يوجد موسم (رمضان / المدارس) خلال النافذة الزمنية",
        ],
    )


def reorder_quantity(velocity_monthly: float, lead_time_days: float, safety_days: float = 14.0) -> int:
    """Simple EOQ-like reorder suggestion: cover lead time + safety buffer."""
    if velocity_monthly <= 0 or lead_time_days <= 0:
        return 0
    daily_velocity = velocity_monthly / 30.0
    cover_days = lead_time_days + safety_days
    return max(0, math.ceil(daily_velocity * cover_days))
