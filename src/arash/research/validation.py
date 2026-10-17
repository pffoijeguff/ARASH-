"""Evidence checks for research reports and reproducible offline backtests."""
from __future__ import annotations
from decimal import Decimal
from typing import Any
from arash.data.validation import validate_candle_series
from arash.domain.models import Candle
from arash.research.backtest import BacktestResult, dataset_fingerprint

def validate_research_dataset(candles: list[Candle]) -> dict[str, Any]:
    items = validate_candle_series(candles)
    digest = dataset_fingerprint(items)
    symbols = sorted({c.symbol for c in items})
    intervals = sorted({c.interval for c in items})
    timestamps = [c.timestamp for c in items]
    return {
        "schema_version": 1, "status": "PASS" if len(symbols) == 1 and len(intervals) == 1 else "BLOCK",
        "candle_count": len(items), "symbol_count": len(symbols), "interval_count": len(intervals),
        "symbols": symbols, "intervals": intervals, "dataset_sha256": digest,
        "first_timestamp_utc": timestamps[0].isoformat(), "last_timestamp_utc": timestamps[-1].isoformat(),
        "strictly_increasing_timestamps": all(a < b for a,b in zip(timestamps,timestamps[1:])),
        "limitations": ["Structural consistency does not verify source authenticity, exchange-session completeness, or correctness of market prices."],
    }

def validate_backtest_accounting(result: BacktestResult, *, tolerance: Decimal = Decimal("1e-12")) -> dict[str, Any]:
    if not tolerance.is_finite() or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    ledger_pnl = sum((trade.net_pnl for trade in result.trades), Decimal("0"))
    difference = result.net_pnl - ledger_pnl
    passed = abs(difference) <= tolerance
    return {
        "schema_version": 1, "status": "PASS" if passed else "BLOCK",
        "strategy": result.strategy, "symbol": result.symbol, "dataset_sha256": result.dataset_sha256,
        "portfolio_net_pnl": str(result.net_pnl), "closed_trade_ledger_net_pnl": str(ledger_pnl),
        "reconciliation_difference": str(difference), "tolerance": str(tolerance),
        "checks": {"trade_ledger_reconciles_to_final_equity": passed,
                   "no_live_orders": True, "leverage_supported": False},
        "note": "Accounting reconciliation validates only the internal arithmetic identity; it is not a profitability or model-validity check.",
    }
