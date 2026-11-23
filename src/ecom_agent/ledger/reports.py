"""Business reports that go beyond the marketplace's own: they join sales
with purchase cost, sourcing channel, expenses and mileage."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from .backends import Ledger

# IRS standard business mileage rate is set per year; keep it configurable.
DEFAULT_MILEAGE_RATE = 0.70


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def profit_by_item(ledger: Ledger) -> list[dict]:
    """True profit per sold item after cost, fees, shipping, extras and refunds."""
    inv = {r["sku"]: r for r in ledger.read("Inventory")}
    out = []
    for s in ledger.read("Sales"):
        item = inv.get(s["sku"], {})
        cost = item.get("cost", 0.0)
        revenue = s["sale_price"] + s["shipping_charged"] - s["refund"]
        profit = revenue - s["fees"] - s["shipping_cost"] - s["other_costs"] - cost
        out.append({
            "sku": s["sku"],
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "source": item.get("source", ""),
            "sale_date": s["sale_date"],
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "profit": round(profit, 2),
            "days_to_sell": (_d(s["sale_date"]) - _d(item["purchase_date"])).days
            if item.get("purchase_date") else None,
        })
    return sorted(out, key=lambda r: r["profit"], reverse=True)


def _group(rows: list[dict], key: str) -> list[dict]:
    g: dict[str, dict] = defaultdict(lambda: {"items": 0, "cost": 0.0, "profit": 0.0, "days": []})
    for r in rows:
        b = g[r[key] or "unknown"]
        b["items"] += 1
        b["cost"] += r["cost"]
        b["profit"] += r["profit"]
        if r["days_to_sell"] is not None:
            b["days"].append(r["days_to_sell"])
    out = []
    for k, b in g.items():
        out.append({
            key: k,
            "items": b["items"],
            "profit": round(b["profit"], 2),
            "profit_per_100_spent": round(100 * b["profit"] / b["cost"], 2) if b["cost"] else None,
            "avg_days_to_sell": round(sum(b["days"]) / len(b["days"]), 1) if b["days"] else None,
        })
    return sorted(out, key=lambda r: r["profit"], reverse=True)


def return_by_category(ledger: Ledger) -> list[dict]:
    """Profit per $100 spent and sell-through speed by category."""
    return _group(profit_by_item(ledger), "category")


def best_sourcing_channels(ledger: Ledger) -> list[dict]:
    """Which places to buy produce the most profit and fastest sales."""
    return _group(profit_by_item(ledger), "source")


def inventory_aging(ledger: Ledger, today: date | None = None) -> dict:
    """Cash tied up in unsold stock, bucketed by age."""
    today = today or date.today()
    buckets = {"0-29": [], "30-59": [], "60-89": [], "90+": []}
    for r in ledger.read("Inventory"):
        if r["status"] not in ("in_stock", "listed") or not r["purchase_date"]:
            continue
        age = (today - _d(r["purchase_date"])).days
        key = "0-29" if age < 30 else "30-59" if age < 60 else "60-89" if age < 90 else "90+"
        buckets[key].append({"sku": r["sku"], "title": r["title"], "cost": r["cost"], "age_days": age})
    return {
        "total_cash_in_stock": round(sum(i["cost"] for b in buckets.values() for i in b), 2),
        "buckets": {k: {"count": len(v), "cost": round(sum(i["cost"] for i in v), 2), "items": v}
                    for k, v in buckets.items()},
    }


def monthly_summary(ledger: Ledger, month: str, mileage_rate: float = DEFAULT_MILEAGE_RATE) -> dict:
    """Revenue, gross and net profit for one month (YYYY-MM)."""
    items = [r for r in profit_by_item(ledger) if r["sale_date"].startswith(month)]
    expenses = sum(e["amount"] for e in ledger.read("Expenses") if e["date"].startswith(month))
    miles = sum(m["miles"] for m in ledger.read("Mileage") if m["date"].startswith(month))
    revenue = sum(i["revenue"] for i in items)
    gross = sum(i["profit"] for i in items)
    net = gross - expenses - miles * mileage_rate
    return {
        "month": month,
        "items_sold": len(items),
        "revenue": round(revenue, 2),
        "gross_profit": round(gross, 2),
        "expenses": round(expenses, 2),
        "mileage_deduction": round(miles * mileage_rate, 2),
        "net_profit": round(net, 2),
        "margin_pct": round(100 * net / revenue, 1) if revenue else 0.0,
        "top_flips": items[:3],
        "bottom_flips": items[-3:][::-1] if len(items) > 3 else [],
    }
