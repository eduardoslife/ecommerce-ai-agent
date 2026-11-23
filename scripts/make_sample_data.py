"""Generate the synthetic demo ledger in data/sample/.

All numbers are made up. The real business ledger is private and never
committed to this repo.

    python scripts/make_sample_data.py
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

from ecom_agent.ledger.schema import TABS
from ecom_agent.pricing import FeeModel

OUT = Path(__file__).resolve().parents[1] / "data" / "sample"
rng = random.Random(42)
fees = FeeModel()

CATALOG = [  # (title, category, brand, typical cost, typical sale)
    ("Canon AE-1 Program 35mm film camera", "camera", "Canon", 90, 210),
    ("Nikon FM2 body", "camera", "Nikon", 180, 360),
    ("Olympus OM-1 with 50mm f/1.8", "camera", "Olympus", 110, 240),
    ("Fujifilm X100V", "camera", "Fujifilm", 900, 1350),
    ("Sony a6000 kit", "camera", "Sony", 220, 380),
    ("Pentax K1000", "camera", "Pentax", 70, 170),
    ("Sony WH-1000XM4 headphones", "audio", "Sony", 110, 190),
    ("Sennheiser HD 600", "audio", "Sennheiser", 160, 290),
    ("Bose QuietComfort 45", "audio", "Bose", 120, 185),
    ("Audio-Technica AT-LP120 turntable", "audio", "Audio-Technica", 150, 260),
    ("Marantz 2230 receiver", "audio", "Marantz", 250, 520),
    ("Nintendo GameCube console", "other_electronics", "Nintendo", 60, 130),
    ("Apple iPad Air (4th gen)", "other_electronics", "Apple", 220, 330),
]
SOURCES = ["estate sale", "Facebook Marketplace", "thrift store", "garage sale", "OfferUp"]


def write(tab: str, rows: list[dict]) -> None:
    with (OUT / f"{tab.lower()}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TABS[tab])
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inventory, sales, report_lines = [], [], []
    start = date(2026, 6, 1)
    for i in range(36):
        title, cat, brand, cost, sale = rng.choice(CATALOG)
        sku = f"DEMO-{i + 1:04d}"
        bought = start + timedelta(days=rng.randint(0, 150))
        cost = round(cost * rng.uniform(0.7, 1.2))
        row = {"sku": sku, "title": title, "category": cat, "brand": brand,
               "source": rng.choice(SOURCES), "purchase_date": bought.isoformat(),
               "cost": cost, "status": "in_stock", "listed_date": "", "list_price": ""}
        if i < 26:  # sold
            listed = bought + timedelta(days=rng.randint(1, 6))
            sold = min(listed + timedelta(days=rng.randint(2, 45)), date(2026, 11, 20))
            price = round(sale * rng.uniform(0.85, 1.15), 2)
            ship_chg = rng.choice([0.0, 0.0, 12.99, 18.50])
            ship_cost = round(rng.uniform(9, 24), 2)
            fee = fees.fees(price, ship_chg)
            refund = price if i == 7 else 0.0  # one returned item
            order = f"26-{10000 + i}-{rng.randint(10000, 99999)}"
            row.update(status="sold", listed_date=listed.isoformat(), list_price=round(price * 1.08, 2))
            sales.append({"order_id": order, "sku": sku, "sale_date": sold.isoformat(),
                          "sale_price": price, "shipping_charged": ship_chg, "shipping_cost": ship_cost,
                          "fees": fee, "other_costs": 0.0, "refund": refund})
            fvf_fixed = 0.40
            report_lines.append({"Transaction creation date": sold.isoformat(), "Type": "Order",
                                 "Order number": order, "Custom label": sku, "Item title": title,
                                 "Item subtotal": price, "Shipping and handling": ship_chg,
                                 "Final Value Fee - fixed": -fvf_fixed,
                                 "Final Value Fee - variable": -round(fee - fvf_fixed, 2),
                                 "Gross transaction amount": round(price + ship_chg, 2),
                                 "Net amount": round(price + ship_chg - fee, 2)})
            report_lines.append({"Transaction creation date": sold.isoformat(), "Type": "Shipping label",
                                 "Order number": order, "Net amount": -ship_cost})
            if refund:
                report_lines.append({"Transaction creation date": (sold + timedelta(days=9)).isoformat(),
                                     "Type": "Refund", "Order number": order,
                                     "Gross transaction amount": -refund, "Net amount": -refund})
        elif i < 31:
            listed = bought + timedelta(days=rng.randint(1, 6))
            row.update(status="listed", listed_date=listed.isoformat(), list_price=round(sale * 1.1, 2))
        inventory.append(row)

    expenses = [{"date": f"2026-{m:02d}-05", "category": "Supplies",
                 "description": "Boxes, bubble wrap, tape", "amount": round(rng.uniform(25, 60), 2)}
                for m in range(6, 12)]
    expenses += [{"date": f"2026-{m:02d}-15", "category": "Software",
                  "description": "Listing and photo tools", "amount": 19.99} for m in range(6, 12)]
    mileage = [{"date": (start + timedelta(days=d)).isoformat(), "purpose": "Sourcing trip",
                "miles": rng.randint(8, 60)} for d in range(0, 170, 9)]

    write("Inventory", inventory)
    write("Sales", sales)
    write("Expenses", expenses)
    write("Mileage", mileage)
    write("ActionLog", [])

    header = ["Transaction creation date", "Type", "Order number", "Custom label", "Item title",
              "Item subtotal", "Shipping and handling", "Final Value Fee - fixed",
              "Final Value Fee - variable", "Gross transaction amount", "Net amount"]
    report_lines.append({"Transaction creation date": "2026-11-01", "Type": "Payout", "Net amount": -999.0})
    with (OUT / "marketplace_transaction_report_sample.csv").open("w", newline="") as f:
        f.write("Transaction report (synthetic sample)\nPeriod: 2026-06-01 to 2026-11-20\n\n")
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(report_lines)

    (OUT / "identification_example.json").write_text(json.dumps({
        "category": "camera", "brand": "Nikon", "model": "FM2", "variant": "chrome body",
        "condition": "Light brassing on top plate corners, no dents visible",
        "identification_confidence": 0.92,
        "observations": [
            {"id": "serial_plate", "result": "pass", "note": "Serial visible on top plate, consistent format"},
            {"id": "print_quality", "result": "pass", "note": "Engravings crisp and even"},
            {"id": "mount_condition", "result": "pass", "note": "Mount clean, normal wear"},
            {"id": "lens_glass", "result": "unclear", "note": "Body only, no lens shown"},
            {"id": "body_match", "result": "pass", "note": "Shutter dial and finder match FM2"},
            {"id": "region_market", "result": "pass", "note": "Standard markings"},
        ],
    }, indent=2))
    print(f"Wrote demo ledger to {OUT}")


if __name__ == "__main__":
    main()
