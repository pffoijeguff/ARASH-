"""Read-only reconciliation of SQLite candle history, lineage and per-market quality."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from arash.data.quality import audit_candles
from arash.storage.sqlite_store import SQLiteStore


def reconcile_market_data(
    store: SQLiteStore,
    *,
    now: datetime | None = None,
    stale_after_intervals: int = 2,
) -> dict[str, Any]:
    if stale_after_intervals < 1:
        raise ValueError("stale_after_intervals must be >= 1")
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    observed_at = observed_at.astimezone(timezone.utc)
    ledger = store.inspect_ledger_integrity()
    markets: list[dict[str, Any]] = []
    has_quality_warnings = False
    has_blocking_quality = False
    for symbol, interval in store.list_candle_market_keys():
        candles = store.list_candles(symbol=symbol, interval=interval)
        quality = audit_candles(candles, now=observed_at, stale_after_intervals=stale_after_intervals)
        state = store.get_market_sync_state("nobitex-public-udf", symbol, interval)
        markets.append({
            "symbol": symbol,
            "interval": interval,
            "candle_count": len(candles),
            "first_timestamp": candles[0].timestamp.isoformat() if candles else None,
            "last_timestamp": candles[-1].timestamp.isoformat() if candles else None,
            "quality": quality,
            "latest_sync_state": state,
        })
        has_quality_warnings = has_quality_warnings or quality["status"] == "WARN"
        has_blocking_quality = has_blocking_quality or quality["status"] == "FAIL" or bool(quality["future_candle"])
    market_series_truncated = int(ledger["markets"]) > len(markets)
    snapshot_integrity_failed = not bool(ledger.get("snapshot_integrity_ok", True))
    unversioned_legacy_data = int(ledger.get("legacy_unversioned_candle_count", 0)) > 0
    blocked = (
        not ledger["physical_integrity_ok"] or not ledger["provenance_integrity_ok"]
        or snapshot_integrity_failed or has_blocking_quality
    )
    status = "BLOCKED" if blocked else (
        "NO_DATA" if not markets else (
            "DEGRADED" if has_quality_warnings or market_series_truncated or unversioned_legacy_data else "READY"
        )
    )
    return {
        "schema_version": 1,
        "reconciliation_version": "16.0.0",
        "observed_at": observed_at.isoformat(),
        "status": status,
        "ledger": ledger,
        "snapshot_integrity": {
            "status": "BLOCKED" if snapshot_integrity_failed else (
                "DEGRADED" if unversioned_legacy_data else "READY"
            ),
            "legacy_unversioned_candle_count": int(ledger.get("legacy_unversioned_candle_count", 0)),
            "snapshot_count": int(ledger.get("market_data_snapshots", 0)),
            "snapshot_observation_count": int(ledger.get("snapshot_observations", 0)),
            "note": "Legacy candles without immutable snapshot coverage are not eligible for strict point-in-time replay until re-imported or re-synced.",
        },
        "market_series_count": len(markets),
        "market_series_total": int(ledger["markets"]),
        "market_series_truncated": market_series_truncated,
        "markets": markets,
        "recommendation": (
            "STOP_RESEARCH_AND_REPAIR_LEDGER" if status == "BLOCKED" else
            "REIMPORT_OR_RESYNC_LEGACY_DATA" if unversioned_legacy_data and status == "DEGRADED" else
            "REVIEW_DATA_WARNINGS" if status == "DEGRADED" else
            "IMPORT_OR_SYNC_MARKET_DATA" if status == "NO_DATA" else
            "LEDGER_RECONCILED_WITHOUT_DETECTED_ISSUES"
        ),
        "orders_submitted": False,
        "trade_action": "NONE",
    }
