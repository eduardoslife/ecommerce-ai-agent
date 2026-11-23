"""Command line: `ecom-agent <command>`.

  serve                         start the MCP server (stdio)
  verdict ...                   photo to buy/pass verdict
  import <report.csv> [--summary-total N] [--commit]
                                import an eBay Transaction report and reconcile
  report <profit|categories|sources|aging|month> [YYYY-MM]
  pending                       list proposals waiting for approval
  approve <id> / reject <id>    the human approval gate
"""

from __future__ import annotations

import argparse
import json
import sys

from . import approvals, importers
from .ledger import reports
from .ledger.backends import ledger_from_env


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["serve"]:
        from .mcp_server import run
        return run()
    if argv[:1] == ["verdict"]:
        from .agent.verdict import main as verdict_main
        return verdict_main(argv[1:])

    p = argparse.ArgumentParser(prog="ecom-agent", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("report")
    imp.add_argument("--summary-total", type=float, help="Net total from the Financial Summary page")
    imp.add_argument("--commit", action="store_true", help="Write new orders to the Sales tab")
    rep = sub.add_parser("report")
    rep.add_argument("kind", choices=["profit", "categories", "sources", "aging", "month"])
    rep.add_argument("month", nargs="?")
    sub.add_parser("pending")
    for name in ("approve", "reject"):
        sub.add_parser(name).add_argument("action_id")
    a = p.parse_args(argv)
    led = ledger_from_env()

    if a.cmd == "import":
        res = importers.import_file(a.report)
        _print(importers.reconcile(res, a.summary_total))
        if a.commit:
            have = {s["order_id"] for s in led.read("Sales")}
            new = [s for s in res.sales if s["order_id"] not in have]
            for s in new:
                led.append("Sales", s)
            print(f"Wrote {len(new)} new orders ({len(res.sales) - len(new)} already in the ledger).")
    elif a.cmd == "report":
        fn = {"profit": reports.profit_by_item, "categories": reports.return_by_category,
              "sources": reports.best_sourcing_channels, "aging": reports.inventory_aging}
        if a.kind == "month":
            if not a.month:
                p.error("report month needs YYYY-MM")
            _print(reports.monthly_summary(led, a.month))
        else:
            _print(fn[a.kind](led))
    elif a.cmd == "pending":
        _print(approvals.pending())
    else:
        _print(approvals.decide(led, a.action_id, approve=(a.cmd == "approve")))


if __name__ == "__main__":
    main()
