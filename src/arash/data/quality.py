"""Deterministic OHLCV data-quality audit for locally stored candle series."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from arash.domain.models import Candle
from arash.data.sessions import MarketSessionCalendar

_INTERVALS = {
    "1m": timedelta(minutes=1), "3m": timedelta(minutes=3), "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15), "30m": timedelta(minutes=30), "1h": timedelta(hours=1),
    "2h": timedelta(hours=2), "4h": timedelta(hours=4), "6h": timedelta(hours=6),
    "12h": timedelta(hours=12), "1d": timedelta(days=1), "1w": timedelta(weeks=1),
}


def audit_candles(
    candles: list[Candle], *, now: datetime | None = None, stale_after_intervals: int = 2,
    calendar: MarketSessionCalendar | None = None,
) -> dict[str, Any]:
    """Audit candles. A supplied calendar suppresses gaps expected during closed sessions.

    Without a calendar, legacy continuous-time gap detection is preserved. Calendar
    schedules are user-declared policy, not proof of the exchange's actual hours.
    """
    if stale_after_intervals < 1:
        raise ValueError("stale_after_intervals must be >= 1")
    if not candles:
        return {
            "status": "FAIL", "symbol": None, "interval": None, "candle_count": 0,
            "first_timestamp": None, "last_timestamp": None, "expected_interval_seconds": None,
            "gap_count": 0, "gaps": [], "future_candle": False, "stale": True,
            "stale_after_intervals": stale_after_intervals,
            "calendar": calendar.to_dict() if calendar else None,
            "warnings": ["No candles found for the requested symbol/interval."],
            "errors": ["Empty dataset."],
        }
    symbol, interval = candles[0].symbol, candles[0].interval
    errors: list[str] = []
    warnings: list[str] = []
    if any(c.symbol != symbol or c.interval != interval for c in candles):
        errors.append("Dataset mixes symbols or intervals.")
    ordered = sorted(candles, key=lambda c: c.timestamp)
    seen: set[datetime] = set()
    for candle in ordered:
        if candle.timestamp in seen:
            errors.append(f"Duplicate timestamp: {candle.timestamp.isoformat()}")
            break
        seen.add(candle.timestamp)
    delta = _INTERVALS.get(interval.lower())
    gaps: list[dict[str, Any]] = []
    if delta is None:
        warnings.append(f"Unknown interval '{interval}'; gap detection disabled for this label.")
    else:
        for previous, current in zip(ordered, ordered[1:]):
            elapsed = current.timestamp - previous.timestamp
            if elapsed > delta:
                expected_count = max(0, int(elapsed.total_seconds() // delta.total_seconds()) - 1)
                expected_times = [previous.timestamp + delta * step for step in range(1, expected_count + 1)]
                missing_times = [
                    timestamp for timestamp in expected_times
                    if calendar is None or calendar.is_open_at(timestamp)
                ]
                if missing_times:
                    gaps.append({
                        "from": previous.timestamp.isoformat(), "to": current.timestamp.isoformat(),
                        "elapsed_seconds": int(elapsed.total_seconds()),
                        "estimated_missing_candles": len(missing_times),
                        "missing_timestamps": [item.isoformat() for item in missing_times],
                    })
        if gaps:
            warnings.append(f"Detected {len(gaps)} time gap(s) in the candle series.")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current_time = current_time.astimezone(timezone.utc)
    last_time = ordered[-1].timestamp
    future = last_time > current_time
    stale = False
    if future:
        warnings.append("Latest candle timestamp is in the future relative to audit time.")
    elif delta is not None:
        stale = current_time - last_time > delta * stale_after_intervals
        if stale:
            warnings.append("Latest candle is stale under the configured interval threshold.")
    status = "FAIL" if errors else ("WARN" if warnings else "PASS")
    return {
        "status": status, "symbol": symbol, "interval": interval, "candle_count": len(ordered),
        "first_timestamp": ordered[0].timestamp.isoformat(), "last_timestamp": last_time.isoformat(),
        "expected_interval_seconds": int(delta.total_seconds()) if delta else None,
        "gap_count": len(gaps), "gaps": gaps, "future_candle": future, "stale": stale,
        "stale_after_intervals": stale_after_intervals,
        "calendar": calendar.to_dict() if calendar else None,
        "warnings": warnings, "errors": errors,
    }
