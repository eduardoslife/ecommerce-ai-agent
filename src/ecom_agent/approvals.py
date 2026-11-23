"""Human approval gate for every write action.

The agent can only *propose* a change (log a purchase, record a sale,
mark an item listed). Proposals wait in a queue file. A person commits
them from the command line with `ecom-agent approve <id>`, a channel the
model has no tool for. Every proposal, approval and rejection is written
to the ActionLog tab, so there is a full audit trail.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from .ledger.backends import Ledger
from .ledger.schema import validate

QUEUE_FILE = Path(os.getenv("APPROVAL_QUEUE", Path.home() / ".ecom_agent" / "pending.json"))

# What each action does to the ledger once approved.
ACTIONS = {
    "log_purchase": ("Inventory", "append"),
    "record_sale": ("Sales", "append"),
    "log_expense": ("Expenses", "append"),
    "update_item": ("Inventory", "update"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(queue: Path) -> dict:
    return json.loads(queue.read_text()) if queue.exists() else {}


def _save(queue: Path, data: dict) -> None:
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text(json.dumps(data, indent=2))


def _log(ledger: Ledger, action_id: str, action: str, status: str, actor: str, details: dict) -> None:
    ledger.append("ActionLog", {
        "timestamp": _now(), "action_id": action_id, "action": action,
        "status": status, "actor": actor, "details": json.dumps(details, sort_keys=True),
    })


def propose(ledger: Ledger, action: str, payload: dict, reason: str = "",
            queue: Path = QUEUE_FILE) -> dict:
    """Stage a change. Nothing is written to the business tabs yet."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}; expected one of {sorted(ACTIONS)}")
    tab, mode = ACTIONS[action]
    if mode == "append":
        problems = validate(tab, payload)
        if problems:
            raise ValueError("; ".join(problems))
    elif not {"sku", "changes"} <= set(payload):
        raise ValueError("update_item needs 'sku' and 'changes'")
    action_id = secrets.token_hex(3)
    data = _load(queue)
    data[action_id] = {"action": action, "payload": payload, "reason": reason,
                       "proposed_at": _now(), "status": "pending"}
    _save(queue, data)
    _log(ledger, action_id, action, "proposed", "agent", payload)
    return {"action_id": action_id, "status": "pending",
            "next_step": f"A person must run: ecom-agent approve {action_id}"}


def pending(queue: Path = QUEUE_FILE) -> dict:
    return {k: v for k, v in _load(queue).items() if v["status"] == "pending"}


def decide(ledger: Ledger, action_id: str, approve: bool, actor: str = "owner",
           queue: Path = QUEUE_FILE) -> dict:
    """Commit or reject a staged change. Called from the CLI, never by the agent."""
    data = _load(queue)
    item = data.get(action_id)
    if not item or item["status"] != "pending":
        raise KeyError(f"no pending action {action_id!r}")
    if approve:
        tab, mode = ACTIONS[item["action"]]
        p = item["payload"]
        if mode == "append":
            ledger.append(tab, p)
        elif not ledger.update(tab, "sku", p["sku"], p["changes"]):
            raise KeyError(f"sku {p['sku']!r} not found in {tab}")
    item["status"] = "approved" if approve else "rejected"
    item["decided_at"] = _now()
    _save(queue, data)
    _log(ledger, action_id, item["action"], item["status"], actor, item["payload"])
    return {"action_id": action_id, "status": item["status"]}
