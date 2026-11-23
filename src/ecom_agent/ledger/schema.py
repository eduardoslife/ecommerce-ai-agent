"""Ledger tabs and their columns.

The same schema is used by the CSV backend (local demo) and the Google
Sheets backend (production), so reports and tools don't care which one
is behind them.
"""

from __future__ import annotations

TABS: dict[str, list[str]] = {
    "Inventory": [
        "sku", "title", "category", "brand", "source", "purchase_date",
        "cost", "status", "listed_date", "list_price",
    ],
    "Sales": [
        "order_id", "sku", "sale_date", "sale_price", "shipping_charged",
        "shipping_cost", "fees", "other_costs", "refund",
    ],
    "Expenses": ["date", "category", "description", "amount"],
    "Mileage": ["date", "purpose", "miles"],
    "ActionLog": ["timestamp", "action_id", "action", "status", "actor", "details"],
}

INVENTORY_STATUSES = {"in_stock", "listed", "sold", "returned", "written_off"}

NUMERIC = {
    "cost", "list_price", "sale_price", "shipping_charged", "shipping_cost",
    "fees", "other_costs", "refund", "amount", "miles",
}


def coerce(row: dict) -> dict:
    """Turn spreadsheet strings into numbers where the column is numeric."""
    out = {}
    for k, v in row.items():
        if k in NUMERIC:
            s = str(v).replace("$", "").replace(",", "").strip()
            out[k] = float(s) if s not in ("", "None") else 0.0
        else:
            out[k] = "" if v is None else str(v).strip()
    return out


def validate(tab: str, row: dict) -> list[str]:
    """Return a list of problems with a row; empty means it's fine."""
    if tab not in TABS:
        return [f"unknown tab {tab!r}"]
    problems = [f"missing column {c!r}" for c in TABS[tab] if c not in row]
    extra = set(row) - set(TABS[tab])
    problems += [f"unexpected column {c!r}" for c in sorted(extra)]
    if tab == "Inventory" and row.get("status") and row["status"] not in INVENTORY_STATUSES:
        problems.append(f"status must be one of {sorted(INVENTORY_STATUSES)}")
    for c in NUMERIC & set(row):
        try:
            float(str(row[c]).replace("$", "").replace(",", "") or 0)
        except ValueError:
            problems.append(f"{c} must be a number, got {row[c]!r}")
    return problems
