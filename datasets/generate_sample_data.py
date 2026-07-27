"""Generate realistic sample data for a Cairo electronics shop.
Produces: products.csv, suppliers.csv, inventory.csv, sales.csv
Run: python generate_sample_data.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

OUT = Path(__file__).resolve().parent
FRONTEND_OUT = OUT.parent / "frontend" / "assets" / "sample-data"
FRONTEND_OUT.mkdir(parents=True, exist_ok=True)

SUPPLIERS = [
    ("S01", "El Nour Supplies", "النور للتوريدات", "+20 100 234 5678", 3, 92),
    ("S02", "El Gomaa Tech", "الجمعة للتكنولوجيا", "+20 111 876 5432", 5, 85),
    ("S03", "Modern Electronics", "الإلكترونيات الحديثة", "+20 122 345 6789", 2, 95),
    ("S04", "Sony Egypt Distribution", "سوني مصر للتوزيع", "+20 100 987 6543", 7, 88),
    ("S05", "Delta Trading Co.", "دلتا للتجارة", "+20 111 234 5670", 4, 79),
]

PRODUCTS = [
    # id, name_en, name_ar, category_en, category_ar, brand, cost, price, supplier, weekly_demand
    ("P001", "Samsung Galaxy A56", "سامسونج جالاكسي A56", "Smartphones", "هواتف ذكية", "Samsung", 5100, 5990, "S01", 11),
    ("P002", "iPhone 16 Pro", "آيفون 16 برو", "Smartphones", "هواتف ذكية", "Apple", 32000, 39990, "S02", 3),
    ("P003", "Xiaomi Redmi Note 14", "شاومي ريدمي نوت 14", "Smartphones", "هواتف ذكية", "Xiaomi", 1500, 1800, "S03", 19),
    ("P004", "Sony WH-1000XM6", "سوني WH-1000XM6", "Audio", "صوتيات", "Sony", 10500, 14990, "S04", 2),
    ("P005", "Samsung Galaxy Tab S10", "سامسونج جالاكسي تاب S10", "Tablets", "تابلت", "Samsung", 11500, 14990, "S01", 4),
    ("P006", "Anker PowerCore 20000", "أنكر باوركور 20000", "Accessories", "إكسسوارات", "Anker", 980, 1450, "S05", 13),
    ("P007", "JBL Flip 7", "جي بي ال فليب 7", "Audio", "صوتيات", "JBL", 3100, 4200, "S05", 2),
    ("P008", "Huawei Watch Fit 4", "هواوي ووتش فيت 4", "Wearables", "أجهزة قابلة للارتداء", "Huawei", 2600, 3500, "S03", 5),
    ("P009", "HP LaserJet Pro M404", "طابعة اتش بي ليزر جيت برو", "Printers", "طابعات", "HP", 7800, 9500, "S01", 0.2),
    ("P010", "Canon EOS R50", "كانون EOS R50", "Cameras", "كاميرات", "Canon", 27500, 32000, "S04", 0.4),
]

INVENTORY = [
    # product_id, current_stock, reorder_point, last_restock
    ("P001", 120, 25, "2026-07-20"),
    ("P002", 30, 8, "2026-07-15"),
    ("P003", 0, 40, "2026-07-05"),
    ("P004", 5, 6, "2026-06-28"),
    ("P005", 20, 8, "2026-07-18"),
    ("P006", 65, 20, "2026-07-22"),
    ("P007", 18, 6, "2026-06-10"),
    ("P008", 40, 10, "2026-07-19"),
    ("P009", 8, 3, "2026-04-12"),
    ("P010", 3, 2, "2026-05-30"),
]

DAYS = 120  # ~4 months of history
START = date.today() - timedelta(days=DAYS)


def seasonality(d: date) -> float:
    """Weekend (Fri/Sat in Egypt) spike + a Ramadan-ish spring spike."""
    mult = 1.0
    if d.weekday() in (4, 5):  # Fri, Sat
        mult *= 1.45
    # Simulate a spring season spike (e.g., Ramadan/Eid period ~March-April)
    if date(2026, 3, 1) <= d <= date(2026, 4, 10):
        mult *= 1.6
    return mult


def main():
    # --- suppliers.csv ---
    sup_rows = [("supplier_id", "supplier_name", "supplier_name_ar", "contact", "lead_time_days", "reliability_score")]
    sup_rows += SUPPLIERS

    # --- products.csv ---
    prod_rows = [("product_id", "product_name", "product_name_ar", "category", "category_ar",
                  "brand", "unit_cost_egp", "selling_price_egp", "supplier_id")]
    for p in PRODUCTS:
        prod_rows.append(p[:-1])

    # --- inventory.csv ---
    inv_rows = [("product_id", "current_stock", "reorder_point", "last_restock_date")]
    inv_rows += INVENTORY

    # --- sales.csv ---
    sales_rows = [("transaction_id", "date", "product_id", "quantity", "unit_price_egp", "discount_egp")]
    tid = 1
    weekly_demand = {p[0]: p[-1] for p in PRODUCTS}
    price = {p[0]: p[7] for p in PRODUCTS}
    for i in range(DAYS):
        d = START + timedelta(days=i)
        for pid, wk in weekly_demand.items():
            daily_lambda = (wk / 7.0) * seasonality(d)
            qty = random.poisson(daily_lambda) if hasattr(random, "poisson") else int(random.expovariate(1 / (daily_lambda + 1e-6)))
            # Redmi Note 14 goes out of stock the last ~3 days
            if pid == "P003" and d > date.today() - timedelta(days=3):
                qty = 0
            if qty <= 0:
                continue
            discount = 0
            if random.random() < 0.12:
                discount = round(price[pid] * random.choice([0.05, 0.10])) * qty
            sales_rows.append((f"T{tid:05d}", d.isoformat(), pid, qty, price[pid], discount))
            tid += 1

    def write(name, rows):
        for base in (OUT, FRONTEND_OUT):
            with open(base / name, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(rows)

    write("suppliers.csv", sup_rows)
    write("products.csv", prod_rows)
    write("inventory.csv", inv_rows)
    write("sales.csv", sales_rows)

    print(f"products.csv:   {len(prod_rows) - 1} rows")
    print(f"suppliers.csv:  {len(sup_rows) - 1} rows")
    print(f"inventory.csv:  {len(inv_rows) - 1} rows")
    print(f"sales.csv:      {len(sales_rows) - 1} rows")


if __name__ == "__main__":
    main()
