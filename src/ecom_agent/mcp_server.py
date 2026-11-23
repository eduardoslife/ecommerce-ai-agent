"""MCP server: gives Claude read access to the business ledger and the
ability to *propose* changes, never to commit them.

Run:  ecom-agent serve          (stdio, for Claude Desktop / Claude Code)

Read tools run freely. Write tools only stage a proposal; a person
approves it with `ecom-agent approve <id>` (see approvals.py).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from mcp.server.mcpserver import MCPServer

from . import approvals
from .agent.verdict import decide
from .ledger import reports
from .ledger.backends import ledger_from_env

server = MCPServer(
    name="ecommerce-ops",
    instructions=(
        "Tools for an e-commerce resale business ledger. Read tools are safe to call. "
        "propose_* tools only stage a change: tell the user the action id and that they "
        "must approve it themselves. Never claim a proposal has been saved to the ledger."
    ),
)
_ledger = None


def ledger():
    global _ledger
    if _ledger is None:
        _ledger = ledger_from_env()
    return _ledger


# ---- read tools -----------------------------------------------------------

@server.tool()
def list_inventory(status: str = "in_stock") -> list[dict]:
    """Items in the Inventory tab with a given status (in_stock, listed, sold, returned, written_off, or 'all')."""
    rows = ledger().read("Inventory")
    return rows if status == "all" else [r for r in rows if r["status"] == status]


@server.tool()
def profit_by_item(limit: int = 20) -> list[dict]:
    """True profit per sold item after cost, fees, shipping and refunds, best first."""
    return reports.profit_by_item(ledger())[:limit]


@server.tool()
def return_by_category() -> list[dict]:
    """Profit per $100 spent and average days to sell, by category."""
    return reports.return_by_category(ledger())


@server.tool()
def best_sourcing_channels() -> list[dict]:
    """Which buying sources produce the most profit and fastest sales."""
    return reports.best_sourcing_channels(ledger())


@server.tool()
def inventory_aging() -> dict:
    """Cash tied up in unsold stock, bucketed 0-29, 30-59, 60-89 and 90+ days."""
    return reports.inventory_aging(ledger())


@server.tool()
def monthly_summary(month: str = "") -> dict:
    """Revenue, gross profit, expenses, mileage and net profit for a month (YYYY-MM). Defaults to this month."""
    return reports.monthly_summary(ledger(), month or date.today().strftime("%Y-%m"))


@server.tool()
def evaluate_deal(identification: dict, asking_price: float, comps: list[float],
                  shipping_cost: float = 15.0) -> dict:
    """Buy/pass verdict from an item identification, the asking price and comparable sale prices."""
    return asdict(decide(identification, asking_price, comps, shipping_cost=shipping_cost))


@server.tool()
def pending_approvals() -> dict:
    """Proposed changes waiting for the owner's approval."""
    return approvals.pending()


# ---- write tools: propose only ---------------------------------------------

@server.tool()
def propose_purchase(sku: str, title: str, category: str, brand: str, source: str,
                     purchase_date: str, cost: float, reason: str = "") -> dict:
    """Stage a new inventory purchase. The owner must approve it before it is written."""
    row = {"sku": sku, "title": title, "category": category, "brand": brand, "source": source,
           "purchase_date": purchase_date, "cost": cost, "status": "in_stock",
           "listed_date": "", "list_price": ""}
    return approvals.propose(ledger(), "log_purchase", row, reason)


@server.tool()
def propose_expense(date: str, category: str, description: str, amount: float) -> dict:
    """Stage a business expense (supplies, shipping materials, tools). Owner approval required."""
    row = {"date": date, "category": category, "description": description, "amount": amount}
    return approvals.propose(ledger(), "log_expense", row)


@server.tool()
def propose_mark_listed(sku: str, listed_date: str, list_price: float) -> dict:
    """Stage marking an inventory item as listed at a price. Owner approval required."""
    payload = {"sku": sku, "changes": {"status": "listed", "listed_date": listed_date,
                                       "list_price": list_price}}
    return approvals.propose(ledger(), "update_item", payload)


def run() -> None:
    server.run("stdio")


if __name__ == "__main__":
    run()
