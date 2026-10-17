"""Causal market-regime diagnostics for offline candle research.

Regime labels for a candle-to-candle return are computed only from candles that
closed before that return starts. This is a descriptive market diagnostic, not a
predictive model or a trading signal.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any

from arash.data.validation import validate_candle_series
from arash.domain.models import Candle, ClosedPaperTrade

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def _decimal(value: Decimal | str | int, label: str) -> Decimal:
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a finite decimal") from exc
    if not parsed.is_finite():
        raise ValueError(f"{label} must be a finite decimal")
    return parsed


def analyze_market_regimes(
    source_candles: list[Candle],
    *,
    lookback: int = 20,
    trend_threshold_pct: Decimal = Decimal("2.0"),
    high_volatility_threshold_pct: Decimal = Decimal("1.0"),
) -> dict[str, Any]:
    """Group close-to-close returns by a prior-only four-state regime heuristic.

    A return ending at candle ``i`` is assigned a regime calculated from closes
    ending at ``i-1``. ``lookback`` is the number of prior closes used to estimate
    trailing drift and realized volatility; volatility is the population standard
    deviation of simple per-candle returns inside that trailing window.
    """
    candles = validate_candle_series(source_candles)
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 3:
        raise ValueError("lookback must be an integer of at least 3 candles")
    trend_threshold = _decimal(trend_threshold_pct, "trend_threshold_pct")
    volatility_threshold = _decimal(high_volatility_threshold_pct, "high_volatility_threshold_pct")
    if trend_threshold <= ZERO:
        raise ValueError("trend_threshold_pct must be greater than zero")
    if volatility_threshold <= ZERO:
        raise ValueError("high_volatility_threshold_pct must be greater than zero")
    if len(candles) <= lookback:
        raise ValueError(f"at least lookback + 1 ({lookback + 1}) candles are required")

    closes = [candle.close for candle in candles]
    buckets: dict[str, list[Decimal]] = defaultdict(list)
    assignments: list[dict[str, str]] = []
    for end_index in range(lookback, len(candles)):
        history = closes[end_index - lookback : end_index]
        trailing_drift_pct = (history[-1] / history[0] - ONE) * HUNDRED
        prior_returns = [history[pos] / history[pos - 1] - ONE for pos in range(1, len(history))]
        mean_return = sum(prior_returns, ZERO) / Decimal(len(prior_returns))
        variance = sum(((item - mean_return) ** 2 for item in prior_returns), ZERO) / Decimal(len(prior_returns))
        volatility_pct = variance.sqrt() * HUNDRED

        if trailing_drift_pct >= trend_threshold:
            regime = "UP_TREND"
        elif trailing_drift_pct <= -trend_threshold:
            regime = "DOWN_TREND"
        elif volatility_pct >= volatility_threshold:
            regime = "RANGE_HIGH_VOLATILITY"
        else:
            regime = "RANGE_LOW_VOLATILITY"

        bar_return_pct = (closes[end_index] / closes[end_index - 1] - ONE) * HUNDRED
        buckets[regime].append(bar_return_pct)
        assignments.append(
            {
                "timestamp_utc": candles[end_index].timestamp.isoformat(),
                "regime": regime,
                "bar_return_pct": str(bar_return_pct),
                "trailing_drift_pct": str(trailing_drift_pct),
                "trailing_realized_volatility_pct": str(volatility_pct),
            }
        )

    summaries: dict[str, dict[str, object]] = {}
    total_points = len(assignments)
    for regime in ("UP_TREND", "DOWN_TREND", "RANGE_HIGH_VOLATILITY", "RANGE_LOW_VOLATILITY"):
        values = buckets.get(regime, [])
        if not values:
            summaries[regime] = {
                "bar_count": 0,
                "coverage_pct": "0",
                "mean_bar_return_pct": None,
                "median_bar_return_pct": None,
                "sum_bar_returns_pct": "0",
                "positive_bar_ratio_pct": None,
                "best_bar_return_pct": None,
                "worst_bar_return_pct": None,
            }
            continue
        positive = sum(1 for value in values if value > ZERO)
        summaries[regime] = {
            "bar_count": len(values),
            "coverage_pct": str(Decimal(len(values)) / Decimal(total_points) * HUNDRED),
            "mean_bar_return_pct": str(sum(values, ZERO) / Decimal(len(values))),
            "median_bar_return_pct": str(median(values)),
            # This is a diagnostic sum of selected returns, not a compounded portfolio return.
            "sum_bar_returns_pct": str(sum(values, ZERO)),
            "positive_bar_ratio_pct": str(Decimal(positive) / Decimal(len(values)) * HUNDRED),
            "best_bar_return_pct": str(max(values)),
            "worst_bar_return_pct": str(min(values)),
        }

    return {
        "algorithm": "causal_trailing_drift_and_realized_volatility_v1",
        "lookback_candles": lookback,
        "trend_threshold_pct": str(trend_threshold),
        "high_volatility_threshold_pct_per_bar": str(volatility_threshold),
        "assignment_rule": "regime_for_return_ending_at_i_uses_closes_only_through_i_minus_1",
        "classifiable_return_count": total_points,
        "regime_count": len(buckets),
        "regimes": summaries,
        "assignments": assignments,
        "limitations": [
            "Heuristic labels are descriptive and thresholds are analyst-configured; regime boundaries are not universal.",
            "Volatility is a non-annualized population standard deviation of simple per-candle returns.",
            "sum_bar_returns_pct is an arithmetic diagnostic over selected bars, not a compound investable return.",
            "The first lookback returns cannot be labeled because there is insufficient prior history.",
            "Regime analysis does not measure any strategy's causal performance within each regime.",
        ],
    }


def attribute_trades_by_entry_regime(
    trades: tuple[ClosedPaperTrade, ...] | list[ClosedPaperTrade],
    regime_analysis: dict[str, Any],
) -> dict[str, object]:
    """Summarize closed strategy trades by the regime known at entry time.

    A whole trade is assigned to its entry regime even if it crosses regime
    boundaries later. This is cohort analysis, not exact per-bar P&L attribution.
    """
    regime_by_timestamp = {
        item["timestamp_utc"]: item["regime"]
        for item in regime_analysis.get("assignments", [])
    }
    grouped: dict[str, list[Decimal]] = defaultdict(list)
    for trade in trades:
        regime = regime_by_timestamp.get(trade.opened_at.isoformat(), "WARMUP_UNCLASSIFIED")
        grouped[regime].append(trade.net_pnl)

    labels = (
        "UP_TREND",
        "DOWN_TREND",
        "RANGE_HIGH_VOLATILITY",
        "RANGE_LOW_VOLATILITY",
        "WARMUP_UNCLASSIFIED",
    )
    output: dict[str, object] = {}
    for label in labels:
        pnl_values = grouped.get(label, [])
        wins = sum(1 for pnl in pnl_values if pnl > ZERO)
        output[label] = {
            "closed_trade_count": len(pnl_values),
            "net_pnl_sum": str(sum(pnl_values, ZERO)),
            "mean_trade_net_pnl": str(sum(pnl_values, ZERO) / Decimal(len(pnl_values))) if pnl_values else None,
            "positive_trade_ratio_pct": str(Decimal(wins) / Decimal(len(pnl_values)) * HUNDRED) if pnl_values else None,
            "best_trade_net_pnl": str(max(pnl_values)) if pnl_values else None,
            "worst_trade_net_pnl": str(min(pnl_values)) if pnl_values else None,
        }
    return {
        "strategy": "sma-crossover",
        "grouping_rule": "entire closed trade is assigned to regime available at its opened_at timestamp",
        "trades_crossing_regime_boundaries_are_not_split": True,
        "cohorts": output,
        "limitations": [
            "This is a descriptive entry-regime cohort analysis, not a causal proof of strategy edge.",
            "A trade's whole P&L is attributed to its entry regime even if it crosses later regimes.",
            "Costs follow the baseline backtest assumptions and fills remain simulated.",
        ],
    }
