"""Import marketplace sales into the ledger and reconcile the totals.

Reads an eBay Seller Hub *Transaction report* CSV (Payments > Reports).
Column names drift between report versions, so each field is matched
against a list of aliases instead of one exact header.

Order lines become Sales rows. Refund and shipping-label lines are folded
into the matching order. Sales tax collected by the marketplace is
ignored, since it never belongs to the seller.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ALIASES = {
    "date": ["transaction creation date", "date"],
    "type": ["type", "transaction type"],
    "order": ["order number", "order id"],
    "sku": ["custom label", "sku"],
    "title": ["item title", "title"],
    "subtotal": ["item subtotal", "subtotal"],
    "shipping": ["shipping and handling", "shipping"],
    "net": ["net amount", "net"],
    "gross": ["gross transaction amount", "gross amount"],
}
FEE_PREFIXES = ("final value fee", "regulatory operating fee", "international fee",
                "very high", "below standard", "promoted listing", "ad fee")


def _num(v: str | None) -> float:
    if v is None:
        return 0.0
    s = str(v).replace("$", "").replace(",", "").strip()
    if s in ("", "--"):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    return -float(s) if neg else float(s)


def _find_header(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        low = line.lower()
        if "type" in low and ("order number" in low or "order id" in low):
            return i
    raise ValueError("could not find the header row; is this an eBay Transaction report?")


@dataclass
class ImportResult:
    sales: list[dict]
    report_net_total: float
    skipped: dict[str, int] = field(default_factory=dict)
    unmatched: list[str] = field(default_factory=list)


def parse_transaction_report(text: str) -> ImportResult:
    lines = text.splitlines()
    start = _find_header(lines)
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    headers = {h.lower().strip(): h for h in (reader.fieldnames or [])}

    def col(row: dict, key: str) -> str | None:
        for alias in ALIASES[key]:
            if alias in headers:
                return row.get(headers[alias])
        return None

    fee_cols = [h for low, h in headers.items() if low.startswith(FEE_PREFIXES)]

    orders: dict[str, dict] = {}
    extras = defaultdict(lambda: {"refund": 0.0, "shipping_cost": 0.0})
    skipped: dict[str, int] = defaultdict(int)
    net_total = 0.0

    for row in reader:
        kind = (col(row, "type") or "").strip().lower()
        order = (col(row, "order") or "").strip()
        net = _num(col(row, "net"))
        if kind == "payout":
            skipped[kind] += 1
            continue
        net_total += net
        if kind == "order":
            fees = sum(abs(_num(row.get(c))) for c in fee_cols)
            o = orders.setdefault(order, {
                "order_id": order, "sku": (col(row, "sku") or "").strip(),
                "sale_date": (col(row, "date") or "")[:10],
                "sale_price": 0.0, "shipping_charged": 0.0, "fees": 0.0,
            })
            o["sale_price"] += _num(col(row, "subtotal"))
            o["shipping_charged"] += _num(col(row, "shipping"))
            o["fees"] += fees
        elif kind == "refund" and order:
            extras[order]["refund"] += abs(_num(col(row, "gross")) or net)
        elif kind == "shipping label" and order:
            extras[order]["shipping_cost"] += abs(net)
        else:
            skipped[kind or "blank"] += 1  # other fees: counted in net_total, booked as expenses

    unmatched = [o for o in extras if o not in orders]
    sales = []
    for oid, o in orders.items():
        e = extras.get(oid, {"refund": 0.0, "shipping_cost": 0.0})
        sales.append({
            "order_id": oid, "sku": o["sku"], "sale_date": o["sale_date"],
            "sale_price": round(o["sale_price"], 2), "shipping_charged": round(o["shipping_charged"], 2),
            "shipping_cost": round(e["shipping_cost"], 2), "fees": round(o["fees"], 2),
            "other_costs": 0.0, "refund": round(e["refund"], 2),
        })
    return ImportResult(sales=sales, report_net_total=round(net_total, 2),
                        skipped=dict(skipped), unmatched=unmatched)


def ledger_net(sales: list[dict]) -> float:
    """What the ledger says the marketplace paid out for these sales."""
    return round(sum(s["sale_price"] + s["shipping_charged"] - s["fees"]
                     - s["shipping_cost"] - s["refund"] for s in sales), 2)


def reconcile(result: ImportResult, summary_total: float | None = None, tolerance: float = 0.01) -> dict:
    """Compare the ledger's numbers with the report and, optionally, with the
    total from the marketplace's Financial Summary page."""
    ours = ledger_net(result.sales)
    other_lines = round(result.report_net_total - ours, 2)
    out = {
        "orders": len(result.sales),
        "ledger_net_from_orders": ours,
        "report_net_total": result.report_net_total,
        "non_order_lines_net": other_lines,  # other fees, credits: book as expenses/income
        "unmatched_refunds_or_labels": result.unmatched,
    }
    if summary_total is not None:
        diff = round(result.report_net_total - summary_total, 2)
        out["financial_summary_total"] = summary_total
        out["difference_vs_summary"] = diff
        out["reconciled"] = abs(diff) <= tolerance and not result.unmatched
    return out


def import_file(path: str | Path) -> ImportResult:
    return parse_transaction_report(Path(path).read_text(encoding="utf-8-sig"))
