"""Pricing math: marketplace fees, comp statistics and profit.

Pure functions with no I/O, so they are easy to test and reuse from the
agent, the MCP server and the reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

# Defaults are configurable assumptions, not a statement of current eBay
# pricing. Check your own category's fee rate and override via FeeModel.
DEFAULT_FINAL_VALUE_RATE = 0.136
DEFAULT_PER_ORDER_FEE = 0.40
DEFAULT_PER_ORDER_FEE_SMALL = 0.30  # orders at or under the small-order threshold
SMALL_ORDER_THRESHOLD = 10.00
MIN_COMPS_FOR_CONFIDENCE = 5


@dataclass(frozen=True)
class FeeModel:
    final_value_rate: float = DEFAULT_FINAL_VALUE_RATE
    per_order_fee: float = DEFAULT_PER_ORDER_FEE
    per_order_fee_small: float = DEFAULT_PER_ORDER_FEE_SMALL
    small_order_threshold: float = SMALL_ORDER_THRESHOLD

    def fees(self, sale_price: float, shipping_charged: float = 0.0) -> float:
        """Marketplace fees on one order. Final value fee applies to the
        total the buyer pays (item plus shipping charged)."""
        total = sale_price + shipping_charged
        fixed = self.per_order_fee_small if total <= self.small_order_threshold else self.per_order_fee
        return round(total * self.final_value_rate + fixed, 2)


@dataclass(frozen=True)
class CompStats:
    count: int
    low: float
    median: float
    high: float

    @property
    def low_confidence(self) -> bool:
        return self.count < MIN_COMPS_FOR_CONFIDENCE


def comp_stats(prices: list[float]) -> CompStats:
    """Summarize comparable prices. Drops non-positive values and trims the
    top and bottom 10% when there are enough comps to absorb outliers."""
    clean = sorted(p for p in prices if p and p > 0)
    if not clean:
        raise ValueError("at least one positive comparable price is required")
    if len(clean) >= 10:
        cut = len(clean) // 10
        clean = clean[cut : len(clean) - cut]
    return CompStats(count=len(clean), low=clean[0], median=round(median(clean), 2), high=clean[-1])


def net_profit(
    sale_price: float,
    cost: float,
    shipping_cost: float = 0.0,
    shipping_charged: float = 0.0,
    other_costs: float = 0.0,
    fee_model: FeeModel | None = None,
) -> float:
    """True profit on one item after cost, fees, shipping and extras
    (insurance, supplies, repairs)."""
    fm = fee_model or FeeModel()
    revenue = sale_price + shipping_charged
    return round(revenue - fm.fees(sale_price, shipping_charged) - shipping_cost - cost - other_costs, 2)


def roi(profit: float, cost: float) -> float:
    """Profit per dollar spent on the item. Returns 0 for zero-cost items
    to avoid dividing by zero (free finds are reported by profit alone)."""
    return round(profit / cost, 4) if cost > 0 else 0.0


def max_buy_price(
    expected_sale: float,
    target_profit: float,
    shipping_cost: float = 0.0,
    fee_model: FeeModel | None = None,
) -> float:
    """Highest price you can pay and still clear the target profit."""
    fm = fee_model or FeeModel()
    return round(max(0.0, expected_sale - fm.fees(expected_sale) - shipping_cost - target_profit), 2)
