"""Descriptive aggregation and risk summaries for independent paper backtests."""
from __future__ import annotations
from decimal import Decimal
from typing import Any, Iterable
from arash.research.backtest import BacktestResult

ZERO = Decimal("0")
HUNDRED = Decimal("100")

def summarize_backtests(results: Iterable[BacktestResult]) -> dict[str, Any]:
    items = list(results)
    seen: set[tuple[str, str, str]] = set()
    rows: list[dict[str, Any]] = []
    for result in items:
        identity = (result.strategy, result.symbol, result.dataset_sha256)
        if identity in seen:
            raise ValueError(f"duplicate strategy result for {identity}")
        seen.add(identity)
        rows.append({
            "strategy": result.strategy, "symbol": result.symbol, "interval": result.interval,
            "dataset_sha256": result.dataset_sha256, "candle_count": result.candle_count,
            "initial_cash": str(result.config.initial_cash), "final_equity": str(result.final_equity),
            "net_pnl": str(result.net_pnl), "return_pct": str(result.return_pct),
            "max_drawdown_pct": str(result.max_drawdown_pct),
            "completed_trades": result.completed_trades,
            "win_rate_pct": str(result.win_rate_pct) if result.win_rate_pct is not None else None,
            "fees": str(result.fees), "estimated_slippage_cost": str(result.estimated_slippage_cost),
            "estimated_spread_cost": str(result.estimated_spread_cost),
            "estimated_market_impact_cost": str(result.estimated_market_impact_cost),
        })
    return {
        "schema_version": 1, "report_type": "independent_backtest_summary",
        "result_count": len(rows), "results": rows,
        "comparison_policy": "Independent strategy results are shown side-by-side; they are not combined as if they were a single multi-asset portfolio.",
        "limitations": [
            "Results are conditional on one dataset and one configuration per strategy.",
            "Different samples, currencies and position sizes are not directly comparable without normalization.",
            "No capital allocation optimization or joint portfolio simulation is performed.",
            "Return and drawdown metrics are simulated and do not establish future performance.",
        ],
        "trade_action": "NONE", "execution_enabled": False,
    }

def aggregate_closed_trade_pnl(results: Iterable[BacktestResult]) -> dict[str, Any]:
    items = list(results)
    pnl = [trade.net_pnl for result in items for trade in result.trades]
    wins = sum(value > ZERO for value in pnl)
    losses = sum(value < ZERO for value in pnl)
    net = sum(pnl, ZERO)
    return {
        "report_type": "closed_trade_pnl_aggregate",
        "trade_count": len(pnl), "winning_trades": wins, "losing_trades": losses,
        "flat_trades": len(pnl) - wins - losses, "net_pnl_sum": str(net),
        "mean_trade_net_pnl": str(net / Decimal(len(pnl))) if pnl else None,
        "positive_trade_ratio_pct": str(Decimal(wins) / Decimal(len(pnl)) * HUNDRED) if pnl else None,
        "aggregation_note": "This is a pooled trade-level description, not a portfolio return because capital overlap and trade concurrency are not reconstructed.",
        "trade_action": "NONE",
    }
