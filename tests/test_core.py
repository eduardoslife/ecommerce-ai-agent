from datetime import date
from pathlib import Path

import pytest

from ecom_agent import approvals, importers
from ecom_agent.agent.authenticity import score
from ecom_agent.agent.verdict import decide
from ecom_agent.ledger import reports
from ecom_agent.ledger.backends import CsvLedger
from ecom_agent.pricing import FeeModel, comp_stats, max_buy_price, net_profit

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


# ---- pricing ----------------------------------------------------------------

def test_fees_use_small_order_fixed_fee():
    fm = FeeModel(final_value_rate=0.10, per_order_fee=0.40, per_order_fee_small=0.30)
    assert fm.fees(8.00) == 1.10
    assert fm.fees(100.00, 10.00) == 11.40


def test_net_profit_and_max_buy_are_consistent():
    fm = FeeModel(final_value_rate=0.10, per_order_fee=0.0)
    ceiling = max_buy_price(300, target_profit=50, shipping_cost=20, fee_model=fm)
    assert ceiling == 200.0
    assert net_profit(300, ceiling, shipping_cost=20, fee_model=fm) == 50.0


def test_comp_stats_flags_thin_data_and_trims_outliers():
    assert comp_stats([100, 120]).low_confidence
    s = comp_stats([10] + [200] * 8 + [5000])
    assert (s.low, s.high, s.count) == (200, 200, 8)
    with pytest.raises(ValueError):
        comp_stats([0, -5])


# ---- authenticity and verdict -----------------------------------------------

def _ident(results, confidence=0.95):
    ids = ["serial_plate", "print_quality", "mount_condition", "lens_glass", "body_match", "region_market"]
    return {"category": "camera", "brand": "Nikon", "model": "FM2", "identification_confidence": confidence,
            "observations": [{"id": i, "result": r, "note": "x"} for i, r in zip(ids, results)]}


def test_missing_observations_count_as_unclear():
    assert score("camera", [])["risk_score"] == 50


def test_two_concerns_mean_high_risk_and_pass():
    v = decide(_ident(["concern", "concern", "pass", "pass", "pass", "pass"]), 100, [400] * 6)
    assert v.risk_level == "high" and v.decision == "PASS"


def test_good_deal_is_buy():
    v = decide(_ident(["pass"] * 6), 100, [350, 360, 340, 355, 345])
    assert v.decision == "BUY"


def test_low_confidence_asks_for_photos():
    assert decide(_ident(["pass"] * 6, confidence=0.4), 100, [350] * 5).decision == "NEED_MORE_PHOTOS"


def test_thin_margin_is_pass_with_offer():
    v = decide(_ident(["pass"] * 6), 300, [320] * 5)
    assert v.decision == "PASS" and v.max_buy_price < 300


# ---- import and reconcile ---------------------------------------------------

def test_sample_report_reconciles_with_ledger():
    res = importers.import_file(SAMPLE / "ebay_transaction_report_sample.csv")
    ledger = CsvLedger(SAMPLE)
    assert len(res.sales) == len(ledger.read("Sales"))
    rec = importers.reconcile(res, summary_total=res.report_net_total)
    assert rec["reconciled"] and rec["non_order_lines_net"] == 0
    assert any(s["refund"] > 0 for s in res.sales)


def test_reconcile_flags_mismatch():
    res = importers.import_file(SAMPLE / "ebay_transaction_report_sample.csv")
    assert not importers.reconcile(res, summary_total=res.report_net_total + 5)["reconciled"]


# ---- reports ---------------------------------------------------------------

def test_reports_run_on_sample():
    led = CsvLedger(SAMPLE)
    items = reports.profit_by_item(led)
    assert items == sorted(items, key=lambda r: r["profit"], reverse=True)
    aging = reports.inventory_aging(led, today=date(2026, 11, 20))
    assert aging["total_cash_in_stock"] > 0
    assert reports.monthly_summary(led, "2026-09")["items_sold"] >= 1


# ---- approval gate ---------------------------------------------------------

def test_proposals_do_not_write_until_approved(tmp_path):
    led = CsvLedger(tmp_path / "ledger")
    q = tmp_path / "q.json"
    row = {"date": "2026-11-01", "category": "Supplies", "description": "Boxes", "amount": 20}
    p = approvals.propose(led, "log_expense", row, queue=q)
    assert led.read("Expenses") == []
    approvals.decide(led, p["action_id"], approve=True, queue=q)
    assert len(led.read("Expenses")) == 1
    statuses = [r["status"] for r in led.read("ActionLog")]
    assert statuses == ["proposed", "approved"]
    with pytest.raises(KeyError):
        approvals.decide(led, p["action_id"], approve=True, queue=q)


def test_invalid_proposal_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        approvals.propose(CsvLedger(tmp_path), "log_expense", {"date": "x"}, queue=tmp_path / "q.json")
