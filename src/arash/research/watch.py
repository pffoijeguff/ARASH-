"""Bounded, auditable market watch snapshots and change diagnostics.

This module reports state transitions and unusual observations. It deliberately emits
no trade signals and has no order/execution integration.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

WATCH_VERSION = "11.0.0"
_BAD_STATUSES = {"BLOCKED", "NO_DATA", "DEGRADED", "INSUFFICIENT_HISTORY"}


def state_from_market_report(market_row: dict[str, Any]) -> dict[str, Any]:
    """Extract comparable state from either a wrapped or direct intelligence report."""
    wrapped_intelligence = market_row.get("intelligence")
    intelligence = wrapped_intelligence if isinstance(wrapped_intelligence, dict) else market_row
    market = market_row.get("market") if isinstance(market_row.get("market"), dict) else {}
    quality_value = market_row.get("data_quality") or intelligence.get("data_quality") or {}
    quality = quality_value if isinstance(quality_value, dict) else {}
    price_value = intelligence.get("price") or market_row.get("price") or {}
    price = price_value if isinstance(price_value, dict) else {}
    returns_value = price.get("returns_pct") or {}
    returns = returns_value if isinstance(returns_value, dict) else {}
    regime_value = intelligence.get("market_regime") or market_row.get("market_regime") or {}
    regime_data = regime_value if isinstance(regime_value, dict) else {}
    dataset_value = market_row.get("dataset") or intelligence.get("dataset") or {}
    dataset = dataset_value if isinstance(dataset_value, dict) else {}
    candle_count_raw = market_row.get("candle_count", dataset.get("candle_count", 0))
    try:
        candle_count = int(candle_count_raw or 0)
    except (TypeError, ValueError):
        candle_count = 0
    return {
        "symbol": str(market.get("symbol", market_row.get("symbol", "UNKNOWN"))),
        "interval": str(market.get("interval", market_row.get("interval", "UNKNOWN"))),
        "status": str(market_row.get("status", "BLOCKED")),
        "dataset_sha256": str(
            market_row.get("dataset_sha256") or dataset.get("sha256") or ""
        ),
        "candle_count": candle_count,
        "latest_timestamp": (
            quality.get("last_timestamp")
            or dataset.get("last_timestamp_utc")
            or dataset.get("last_timestamp")
        ),
        "last_close": price.get("last_close"),
        "one_bar_return_pct": returns.get("1_bar_pct"),
        "regime": regime_data.get("latest_causally_assigned_regime"),
        "stale": bool(quality.get("stale", False)),
        "future_candle": bool(quality.get("future_candle", False)),
        "gap_count": int(quality.get("gap_count") or 0),
        "error_count": len(quality.get("errors") or []),
        "warning_count": len(market_row.get("warnings") or quality.get("warnings") or []),
    }

def evaluate_state_change(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    price_move_threshold_pct: Decimal = Decimal("5.0"),
) -> list[dict[str, Any]]:
    """Return edge-triggered diagnostic alerts and important baseline conditions."""
    if not price_move_threshold_pct.is_finite() or price_move_threshold_pct <= 0:
        raise ValueError("price_move_threshold_pct must be a finite positive number")

    alerts: list[dict[str, Any]] = []
    symbol = current.get("symbol", "UNKNOWN")
    interval = current.get("interval", "UNKNOWN")
    context = {"symbol": symbol, "interval": interval}
    new_status = current.get("status")
    if previous is None:
        if new_status != "READY":
            severity = "error" if new_status in {"BLOCKED", "NO_DATA"} else "warning"
            alerts.append({
                **context, "type": "INITIAL_MARKET_STATUS", "severity": severity,
                "current": new_status,
                "message": "The first observed market snapshot is not READY; inspect data availability and quality before relying on it.",
            })
        if current.get("future_candle"):
            alerts.append({
                **context, "type": "FUTURE_CANDLE_BLOCK", "severity": "error",
                "message": "A candle timestamp is later than the watch clock; the affected analysis must remain blocked.",
            })
        if current.get("stale"):
            alerts.append({
                **context, "type": "DATA_BECAME_STALE", "severity": "warning",
                "message": "The latest candle is already beyond the configured freshness threshold at baseline.",
            })
        if int(current.get("gap_count") or 0) > 0:
            alerts.append({
                **context, "type": "DATA_GAPS_DETECTED", "severity": "warning",
                "gap_count": int(current.get("gap_count") or 0),
                "message": "The baseline candle history contains one or more interval gaps; missing candles are not synthesized.",
            })
        # A large one-bar move is an observable condition even when establishing the first baseline.
        current_return = current.get("one_bar_return_pct")
        if current_return is not None:
            try:
                initial_move = Decimal(str(current_return))
            except (InvalidOperation, ValueError):
                initial_move = None
            if initial_move is not None and initial_move.is_finite() and abs(initial_move) >= price_move_threshold_pct:
                alerts.append({
                    **context, "type": "LARGE_ONE_BAR_MOVE", "severity": "warning",
                    "move_pct": str(initial_move), "threshold_pct": str(price_move_threshold_pct),
                    "latest_timestamp": current.get("latest_timestamp"),
                    "message": "The baseline one-bar close-to-close move exceeded the configured threshold; verify venue, interval, and source data.",
                })
        return alerts

    old_status = previous.get("status")
    if old_status != new_status:
        recovered = old_status in _BAD_STATUSES and new_status == "READY"
        alerts.append({
            **context,
            "type": "MARKET_STATUS_RECOVERED" if recovered else "MARKET_STATUS_CHANGED",
            "severity": "info" if recovered else ("error" if new_status in {"BLOCKED", "NO_DATA"} else "warning"),
            "previous": old_status,
            "current": new_status,
            "message": "Market data status changed; inspect data-quality findings before relying on the analysis.",
        })

    same_or_new_data = (
        current.get("latest_timestamp") != previous.get("latest_timestamp")
        or current.get("dataset_sha256") != previous.get("dataset_sha256")
    )
    old_regime, new_regime = previous.get("regime"), current.get("regime")
    if same_or_new_data and old_regime and new_regime and old_regime != new_regime:
        alerts.append({
            **context, "type": "REGIME_CHANGED", "severity": "info",
            "previous": old_regime, "current": new_regime,
            "message": "The descriptive regime label changed between observed snapshots; this is not a forecast or trade signal.",
        })

    if same_or_new_data and current.get("one_bar_return_pct") is not None:
        try:
            move = Decimal(str(current["one_bar_return_pct"]))
        except (InvalidOperation, ValueError):
            move = None
        if move is not None and move.is_finite() and abs(move) >= price_move_threshold_pct:
            alerts.append({
                **context, "type": "LARGE_ONE_BAR_MOVE", "severity": "warning",
                "move_pct": str(move), "threshold_pct": str(price_move_threshold_pct),
                "latest_timestamp": current.get("latest_timestamp"),
                "message": "One-bar close-to-close move exceeded the configured observation threshold; verify venue, interval, and source data.",
            })

    old_stale = bool(previous.get("stale", False))
    if current.get("stale") and not old_stale:
        alerts.append({
            **context, "type": "DATA_BECAME_STALE", "severity": "warning",
            "message": "The latest candle crossed the configured freshness threshold.",
        })
    elif old_stale and not current.get("stale"):
        alerts.append({
            **context, "type": "DATA_FRESHNESS_RECOVERED", "severity": "info",
            "message": "The latest candle is no longer beyond the configured freshness threshold.",
        })

    old_gap = int(previous.get("gap_count") or 0)
    new_gap = int(current.get("gap_count") or 0)
    if new_gap > old_gap and same_or_new_data:
        alerts.append({
            **context, "type": "DATA_GAPS_DETECTED", "severity": "warning",
            "previous_gap_count": old_gap, "gap_count": new_gap,
            "message": "The candle history contains new or additional interval gaps; missing candles are not synthesized.",
        })
    elif old_gap > 0 and new_gap == 0:
        alerts.append({
            **context, "type": "DATA_GAPS_CLEARED", "severity": "info",
            "message": "The current audited candle history no longer contains the previously observed gap condition.",
        })

    if current.get("future_candle") and not bool(previous.get("future_candle", False)):
        alerts.append({
            **context, "type": "FUTURE_CANDLE_BLOCK", "severity": "error",
            "message": "A candle timestamp is later than the watch clock; the affected analysis must remain blocked.",
        })
    return alerts
