"""Photo -> buy/pass verdict.

Coordinator flow (see docs/architecture.md):
  1. Identifier: Claude vision names the brand, model, condition and checks
     each authenticity checklist item it can see.
  2. Authenticity checker: turns those observations into a risk score.
  3. Pricer: summarizes comps and works out profit and max buy price.
  4. Coordinator: combines them into BUY, PASS or NEED_MORE_PHOTOS.

v1 takes price comps as input (typed in, or from your own sales history).
Once eBay API access is approved, the Browse API fills them in.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from ..pricing import FeeModel, comp_stats, max_buy_price, net_profit, roi
from .authenticity import load_checklist, score

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

IDENTIFY_TOOL = {
    "name": "report_identification",
    "description": "Report what the item in the photo is and what the authenticity checks show.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["camera", "audio", "other_electronics"]},
            "brand": {"type": "string"},
            "model": {"type": "string"},
            "variant": {"type": "string", "description": "Color, kit lens, edition, etc. Empty if unknown."},
            "condition": {"type": "string", "description": "Visible condition only. No guesses about function."},
            "identification_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "observations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "result": {"type": "string", "enum": ["pass", "unclear", "concern"]},
                        "note": {"type": "string"},
                    },
                    "required": ["id", "result", "note"],
                },
            },
        },
        "required": ["category", "brand", "model", "condition", "identification_confidence", "observations"],
    },
}

SYSTEM = """You identify used electronics from photos for a resale business.
Only state what is visible. If you cannot read a model number or see a
detail, say so and mark the check "unclear" rather than guessing. Never
call an item authentic or fake; report observations per checklist item."""


def identify(image_path: str | Path) -> dict:
    """Run the Identifier agent on one photo with Claude vision."""
    import anthropic

    path = Path(image_path)
    media = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    image_b64 = base64.standard_b64encode(path.read_bytes()).decode()
    checklists = {c: load_checklist(c) for c in ("camera", "audio", "other_electronics")}
    prompt = (
        "Identify this item, then go through the checklist for its category and report "
        "one observation per check id.\n\nChecklists:\n" + json.dumps(checklists, indent=1)
    )
    resp = anthropic.Anthropic().messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM,
        tools=[IDENTIFY_TOOL],
        tool_choice={"type": "tool", "name": "report_identification"},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media, "data": image_b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return next(b.input for b in resp.content if b.type == "tool_use")


@dataclass
class Verdict:
    decision: str            # BUY, PASS or NEED_MORE_PHOTOS
    item: str
    asking_price: float
    expected_sale: float
    comp_range: str
    comp_count: int
    profit_at_asking: float
    roi_at_asking: float
    max_buy_price: float
    risk_score: int
    risk_level: str
    reasons: list[str]
    closeups_needed: list[str]


def decide(
    identification: dict,
    asking_price: float,
    comps: list[float],
    shipping_cost: float = 15.0,
    min_profit: float = 40.0,
    min_roi: float = 0.30,
    fee_model: FeeModel | None = None,
) -> Verdict:
    """Coordinator: combine identification, authenticity risk and pricing."""
    risk = score(identification["category"], identification.get("observations", []))
    stats = comp_stats(comps)
    expected = stats.median
    profit = net_profit(expected, asking_price, shipping_cost=shipping_cost, fee_model=fee_model)
    r = roi(profit, asking_price)
    ceiling = max_buy_price(expected, min_profit, shipping_cost=shipping_cost, fee_model=fee_model)

    reasons: list[str] = []
    if identification.get("identification_confidence", 0) < 0.7:
        reasons.append("Model not confidently identified from this photo")
    if stats.low_confidence:
        reasons.append(f"Only {stats.count} comps; price estimate is rough")
    reasons += [f"Authenticity concern: {c}" for c in risk["concerns"]]

    if identification.get("identification_confidence", 0) < 0.7 or (
        risk["risk_level"] == "medium" and risk["closeups_needed"]
    ):
        decision = "NEED_MORE_PHOTOS"
    elif risk["risk_level"] == "high":
        decision = "PASS"
        reasons.insert(0, "Authenticity risk is high")
    elif profit >= min_profit and r >= min_roi:
        decision = "BUY"
        reasons.insert(0, f"Clears ${min_profit:.0f} profit and {min_roi:.0%} return at the asking price")
    else:
        decision = "PASS"
        reasons.insert(0, f"Profit ${profit:.2f} at asking is below target; offer up to ${ceiling:.2f}")

    name = " ".join(x for x in (identification.get("brand"), identification.get("model"),
                                identification.get("variant")) if x)
    return Verdict(
        decision=decision, item=name, asking_price=asking_price, expected_sale=expected,
        comp_range=f"${stats.low:.0f}-${stats.high:.0f}", comp_count=stats.count,
        profit_at_asking=profit, roi_at_asking=r, max_buy_price=ceiling,
        risk_score=risk["risk_score"], risk_level=risk["risk_level"],
        reasons=reasons, closeups_needed=risk["closeups_needed"],
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Photo to buy/pass verdict")
    p.add_argument("photo", nargs="?", help="Photo of the item (needs ANTHROPIC_API_KEY)")
    p.add_argument("--asking", type=float, required=True, help="Seller's asking price")
    p.add_argument("--comps", required=True, help="Comparable sale prices, comma-separated")
    p.add_argument("--shipping", type=float, default=15.0)
    p.add_argument("--identification", help="Use a saved identification JSON instead of calling Claude (demo/offline)")
    a = p.parse_args(argv)
    if a.identification:
        ident = json.loads(Path(a.identification).read_text())
    elif a.photo:
        ident = identify(a.photo)
    else:
        p.error("give a photo or --identification")
    comps = [float(x) for x in a.comps.split(",") if x.strip()]
    print(json.dumps(asdict(decide(ident, a.asking, comps, shipping_cost=a.shipping)), indent=2))


if __name__ == "__main__":
    main()
