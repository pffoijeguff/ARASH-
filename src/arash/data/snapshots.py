"""Canonical, reproducible point-in-time data snapshot primitives.

The default availability policy assumes candle timestamps denote bar-open time:
``available_at = timestamp + interval duration``. This is deliberately explicit;
unknown intervals are rejected rather than assigned an invented duration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Mapping

from arash.domain.models import Candle

SNAPSHOT_SCHEMA_VERSION = 1
AVAILABILITY_POLICY = "BAR_OPEN_PLUS_INTERVAL_V1"
INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "3h": 10800,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
    "2d": 172800,
    "3d": 259200,
}



SNAPSHOT_MANIFEST_FIELDS: tuple[str, ...] = (
    "snapshot_id", "source", "symbol", "interval", "snapshot_type", "captured_at",
    "requested_from", "requested_to", "event_time_min", "event_time_max",
    "source_digest_sha256", "source_digest_kind", "normalized_data_sha256", "row_count",
    "availability_policy", "parent_snapshot_id", "new_observation_count",
    "revised_observation_count", "unchanged_observation_count", "recorded_at",
)


def snapshot_manifest_digest(snapshot: Mapping[str, object]) -> str:
    """Hash snapshot metadata that controls provenance and point-in-time semantics.

    The stored digest itself is deliberately excluded. A hash is a tamper-evident check,
    not a signature or externally anchored proof of authenticity.
    """
    try:
        payload = {
            field: (int(snapshot[field]) if field in {
                "row_count", "new_observation_count", "revised_observation_count",
                "unchanged_observation_count",
            } else snapshot[field])
            for field in SNAPSHOT_MANIFEST_FIELDS
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("snapshot metadata is incomplete or invalid") from exc
    if not isinstance(payload["snapshot_id"], str) or not payload["snapshot_id"]:
        raise ValueError("snapshot metadata is missing its identity")
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_decimal(value: Decimal) -> str:
    """Render an exact decimal consistently, without irrelevant trailing zeroes."""
    if not value.is_finite():
        raise ValueError("snapshot decimals must be finite")
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("snapshot timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def candle_available_at(candle: Candle) -> datetime:
    """Conservatively estimate when a bar is observable under the declared policy."""
    seconds = INTERVAL_SECONDS.get(candle.interval.lower())
    if seconds is None:
        raise ValueError(
            f"cannot infer point-in-time availability for unknown interval {candle.interval!r}; "
            "register an explicit interval policy first"
        )
    return candle.timestamp + timedelta(seconds=seconds)


def canonical_candle_records(candles: Iterable[Candle]) -> list[dict[str, str]]:
    """Return normalized observation records for stable content addressing."""
    items = list(candles)
    items.sort(key=lambda item: (item.symbol, item.interval, item.timestamp))
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for candle in items:
        timestamp = utc_iso(candle.timestamp)
        key = (candle.symbol, candle.interval, timestamp)
        if key in seen:
            raise ValueError(f"duplicate candle key in snapshot: {key}")
        seen.add(key)
        records.append({
            "symbol": candle.symbol,
            "interval": candle.interval,
            "event_timestamp": timestamp,
            "open": canonical_decimal(candle.open),
            "high": canonical_decimal(candle.high),
            "low": canonical_decimal(candle.low),
            "close": canonical_decimal(candle.close),
            "volume": canonical_decimal(candle.volume),
            "available_at": utc_iso(candle_available_at(candle)),
        })
    return records


def normalized_candle_sha256(candles: Iterable[Candle]) -> str:
    records = canonical_candle_records(candles)
    raw = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
