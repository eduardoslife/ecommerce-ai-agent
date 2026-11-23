"""Authenticity risk scoring.

The model reports what it can see for each checklist item ("pass",
"concern" or "unclear"). This module turns that into a 0-100 risk score
with reasons. It never says "authentic": it says how risky the item
looks and what close-ups would settle it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_DATA = Path(__file__).resolve().parents[3] / "data"
# The public repo ships generic starter checklists. Real, brand-specific
# checklists live in data/private/ (git-ignored) or wherever
# CHECKLISTS_PATH points, and are used automatically when present.
PUBLIC_CHECKLISTS = _DATA / "checklists" / "checklists.json"
PRIVATE_CHECKLISTS = _DATA / "private" / "checklists.json"
RESULT_WEIGHT = {"pass": 0.0, "unclear": 0.5, "concern": 1.0}


def checklists_path() -> Path:
    if os.getenv("CHECKLISTS_PATH"):
        return Path(os.environ["CHECKLISTS_PATH"]).expanduser()
    return PRIVATE_CHECKLISTS if PRIVATE_CHECKLISTS.exists() else PUBLIC_CHECKLISTS


def load_checklist(category: str) -> list[dict]:
    data = json.loads(checklists_path().read_text())
    return data.get(category) or data["other_electronics"]


def score(category: str, observations: list[dict]) -> dict:
    """observations: [{"id": "...", "result": "pass|unclear|concern", "note": "..."}]

    Checks the model skipped count as "unclear", so a blurry photo can't
    produce a low-risk score by saying nothing.
    """
    checklist = load_checklist(category)
    seen = {o["id"]: o for o in observations}
    total = sum(c["weight"] for c in checklist)
    risk = 0.0
    reasons, closeups = [], []
    for c in checklist:
        obs = seen.get(c["id"], {"result": "unclear", "note": "not visible in photo"})
        w = RESULT_WEIGHT.get(obs["result"], 0.5)
        risk += w * c["weight"]
        if obs["result"] == "concern":
            reasons.append(f"{c['check']}: {obs.get('note', '')}".strip(": "))
        elif obs["result"] != "pass":
            closeups.append(c["check"])
    pct = round(100 * risk / total) if total else 100
    level = "high" if pct >= 50 or len(reasons) >= 2 else "medium" if pct >= 25 or reasons else "low"
    return {"risk_score": pct, "risk_level": level, "concerns": reasons, "closeups_needed": closeups}
