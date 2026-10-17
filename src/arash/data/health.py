"""Bounded raw-CSV market-data health checks before ingestion or research.

This module deliberately audits source rows instead of relying only on Candle objects,
which may already have been normalized or deduplicated by an upstream database.
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from arash.domain.models import Candle

_INTERVALS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1), "3m": timedelta(minutes=3), "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15), "30m": timedelta(minutes=30), "1h": timedelta(hours=1),
    "2h": timedelta(hours=2), "3h": timedelta(hours=3), "4h": timedelta(hours=4),
    "6h": timedelta(hours=6), "12h": timedelta(hours=12), "1d": timedelta(days=1),
    "2d": timedelta(days=2), "3d": timedelta(days=3), "1w": timedelta(weeks=1),
}
_REQUIRED = {"timestamp", "symbol", "interval", "open", "high", "low", "close", "volume"}
_MAX_REPORTED_ROWS = 100


def _empty_report(path: Path, digest: str | None, size: int | None, status: str,
                  message: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "health_engine_version": "8.0.0",
        "status": status,
        "source": {"path": str(path), "sha256": digest, "size_bytes": size},
        "dataset": {
            "raw_rows": 0, "valid_rows": 0, "invalid_rows": 0,
            "symbols": [], "intervals": [], "first_timestamp": None,
            "last_timestamp": None, "timestamp_span_seconds": None,
        },
        "checks": {
            "required_columns_present": False, "duplicate_timestamps": 0,
            "out_of_order_rows": 0, "mixed_symbols_or_intervals": False,
            "future_timestamps": 0, "gap_count": 0, "estimated_missing_candles": 0,
            "stale": None, "age_seconds": None, "unknown_interval": False,
            "file_size_within_limit": size is not None,
        },
        "gaps": [], "row_errors": [], "row_error_count": 0,
        "row_errors_truncated": False,
        "warnings": [message], "blocking_reasons": [message],
        "readiness": {
            "research_allowed_by_health_gate": False,
            "live_execution_allowed": False,
            "recommendation": "REPAIR_SOURCE_DATA_BEFORE_RESEARCH" if status == "BLOCKED" else "NO_DATA",
        },
        "mode": "pre_ingestion_local_csv_audit",
        "orders_submitted": False,
        "trade_action": "NONE",
    }


def audit_csv_health(
    path: str | Path,
    *,
    now: datetime | None = None,
    stale_after_intervals: int = 2,
    max_file_bytes: int = 50_000_000,
    max_rows: int = 1_000_000,
) -> dict[str, Any]:
    """Audit an OHLCV CSV and provide a conservative readiness classification.

    READY means no detected structural issues. DEGRADED means research should pause for
    review (for example gaps/stale data). BLOCKED means structural data problems were found.
    NO_DATA means a valid CSV container has no usable candle rows.
    """
    csv_path = Path(path)
    if stale_after_intervals < 1:
        raise ValueError("stale_after_intervals must be >= 1")
    if max_file_bytes < 1 or max_file_bytes > 100_000_000:
        raise ValueError("max_file_bytes must be between 1 and 100000000")
    if max_rows < 1 or max_rows > 1_000_000:
        raise ValueError("max_rows must be between 1 and 1000000")
    audit_time = now or datetime.now(timezone.utc)
    if audit_time.tzinfo is None or audit_time.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    audit_time = audit_time.astimezone(timezone.utc)

    if not csv_path.is_file():
        raise ValueError(f"CSV file does not exist: {csv_path}")
    size = csv_path.stat().st_size
    if size > max_file_bytes:
        report = _empty_report(csv_path, None, size, "BLOCKED",
                               f"File exceeds the configured size cap ({max_file_bytes} bytes).")
        report["checks"]["file_size_within_limit"] = False
        report["checks"]["max_file_bytes"] = max_file_bytes
        return report
    try:
        raw = csv_path.read_bytes()
    except OSError:
        raise
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        report = _empty_report(csv_path, digest, size, "BLOCKED", "CSV is not valid UTF-8 text.")
        report["checks"]["file_size_within_limit"] = True
        return report

    warnings: list[str] = []
    blocking: list[str] = []
    row_errors: list[dict[str, Any]] = []
    row_error_count = 0
    candles: list[Candle] = []
    raw_rows = 0
    out_of_order = 0
    previous_input_timestamp: datetime | None = None
    duplicate_keys: set[tuple[str, str, datetime]] = set()
    duplicate_timestamps = 0

    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames is None:
            report = _empty_report(csv_path, digest, size, "NO_DATA", "CSV has no header row.")
            report["checks"]["file_size_within_limit"] = True
            return report
        normalized_header_list = [name.strip().lower() for name in reader.fieldnames if name is not None]
        normalized_headers = set(normalized_header_list)
        duplicate_headers = sorted({name for name in normalized_header_list if normalized_header_list.count(name) > 1})
        missing_headers = sorted(_REQUIRED - normalized_headers)
        if duplicate_headers:
            blocking.append("Duplicate column names after normalization: " + ", ".join(duplicate_headers))
        if missing_headers:
            blocking.append("Missing required columns: " + ", ".join(missing_headers))
        required_present = not missing_headers and not duplicate_headers
        if not required_present:
            report = _empty_report(csv_path, digest, size, "BLOCKED", "; ".join(blocking))
            report["checks"].update({
                "required_columns_present": False,
                "duplicate_headers": duplicate_headers,
                "missing_headers": missing_headers,
                "file_size_within_limit": True,
            })
            return report

        for row_number, raw_row in enumerate(reader, start=2):
            if row_number - 1 > max_rows:
                blocking.append(f"Row limit exceeded (maximum {max_rows} data rows).")
                break
            row = {
                (key.strip().lower() if key else ""): (value.strip() if value else "")
                for key, value in raw_row.items() if key is not None
            }
            if not any(row.values()) and raw_row.get(None) is None:
                continue
            raw_rows += 1
            try:
                if raw_row.get(None):
                    raise ValueError("row contains more fields than the header")
                timestamp_text = row["timestamp"]
                if not timestamp_text:
                    raise ValueError("timestamp is empty")
                timestamp = datetime.fromisoformat(
                    timestamp_text[:-1] + "+00:00" if timestamp_text.endswith("Z") else timestamp_text
                )
                if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                    raise ValueError("timestamp must include a timezone")
                timestamp = timestamp.astimezone(timezone.utc)
                symbol, interval = row["symbol"].strip(), row["interval"].strip()
                if not symbol or not interval:
                    raise ValueError("symbol and interval must not be empty")
                values: dict[str, Decimal] = {}
                for name in ("open", "high", "low", "close", "volume"):
                    try:
                        values[name] = Decimal(row[name])
                    except (InvalidOperation, KeyError) as exc:
                        raise ValueError(f"{name} is not a valid decimal") from exc
                    if not values[name].is_finite():
                        raise ValueError(f"{name} must be finite")
                candle = Candle(symbol=symbol, interval=interval, timestamp=timestamp, **values)
                key = (symbol, interval, timestamp)
                if key in duplicate_keys:
                    duplicate_timestamps += 1
                duplicate_keys.add(key)
                if previous_input_timestamp is not None and timestamp <= previous_input_timestamp:
                    out_of_order += 1
                previous_input_timestamp = timestamp
                candles.append(candle)
            except (ValueError, TypeError) as exc:
                row_error_count += 1
                if len(row_errors) < _MAX_REPORTED_ROWS:
                    row_errors.append({"line": row_number, "error": str(exc)[:300]})
    except csv.Error as exc:
        blocking.append(f"CSV parsing error: {str(exc)[:300]}")

    if not raw_rows and not candles and not row_error_count:
        report = _empty_report(csv_path, digest, size, "NO_DATA", "CSV contains no candle data rows.")
        report["checks"]["file_size_within_limit"] = True
        report["checks"]["required_columns_present"] = True
        return report

    symbols = sorted({c.symbol for c in candles})
    intervals = sorted({c.interval for c in candles})
    mixed = len(symbols) > 1 or len(intervals) > 1
    if row_error_count:
        blocking.append(f"{row_error_count} row(s) failed validation; invalid rows are not safe for research.")
    if duplicate_timestamps:
        blocking.append(f"Found {duplicate_timestamps} duplicate timestamp row(s).")
    if out_of_order:
        blocking.append(f"Found {out_of_order} out-of-order timestamp transition(s).")
    if mixed:
        blocking.append("Dataset mixes multiple symbols or intervals; audit one homogeneous series at a time.")
    if any("Row limit exceeded" in item for item in blocking):
        pass

    ordered = sorted(candles, key=lambda item: item.timestamp)
    delta = _INTERVALS.get(intervals[0].lower()) if len(intervals) == 1 else None
    unknown_interval = len(intervals) == 1 and delta is None
    gaps: list[dict[str, Any]] = []
    gap_count = 0
    estimated_missing = 0
    if len(candles) and unknown_interval:
        warnings.append(f"Unknown interval '{intervals[0]}'; gap and freshness thresholds cannot be inferred.")
    if delta is not None and not mixed:
        for previous, current in zip(ordered, ordered[1:]):
            elapsed = current.timestamp - previous.timestamp
            if elapsed > delta:
                gap_count += 1
                missing = max(1, int(elapsed.total_seconds() // delta.total_seconds()) - 1)
                estimated_missing += missing
                if len(gaps) < 100:
                    gaps.append({
                        "from": previous.timestamp.isoformat(), "to": current.timestamp.isoformat(),
                        "elapsed_seconds": int(elapsed.total_seconds()),
                        "estimated_missing_candles": missing,
                    })
        if estimated_missing:
            warnings.append(f"Detected {gap_count} time gap(s), with about {estimated_missing} missing candle(s).")

    future_count = sum(1 for candle in candles if candle.timestamp > audit_time)
    if future_count:
        blocking.append(f"Found {future_count} candle timestamp(s) after audit time.")
    first_time = ordered[0].timestamp if ordered else None
    last_time = ordered[-1].timestamp if ordered else None
    span_seconds = int((last_time - first_time).total_seconds()) if first_time and last_time else None
    age_seconds = int((audit_time - last_time).total_seconds()) if last_time else None
    stale: bool | None = None
    if last_time and delta is not None:
        stale = age_seconds is not None and age_seconds > delta.total_seconds() * stale_after_intervals
        if stale:
            warnings.append("Latest timestamp is stale under the configured interval threshold.")
    elif last_time and delta is None:
        stale = None

    if len(ordered) >= 20:
        close_values = [c.close for c in ordered]
        flat_transitions = sum(1 for left, right in zip(close_values, close_values[1:]) if left == right)
        flat_ratio = flat_transitions / max(1, len(close_values) - 1)
        if flat_ratio >= 0.95:
            warnings.append("At least 95% of adjacent closes are identical; inspect for stale or placeholder values.")
    else:
        flat_ratio = None

    if not candles:
        status = "BLOCKED" if blocking or row_error_count else "NO_DATA"
        if not blocking and status == "NO_DATA":
            warnings.append("No valid candle rows were found.")
    elif blocking:
        status = "BLOCKED"
    elif warnings:
        status = "DEGRADED"
    else:
        status = "READY"

    if status != "READY" and not blocking and not warnings:
        warnings.append("Dataset is not ready for downstream use.")
    report: dict[str, Any] = {
        "schema_version": 1,
        "health_engine_version": "8.0.0",
        "status": status,
        "audited_at": audit_time.isoformat(),
        "source": {"path": str(csv_path), "sha256": digest, "size_bytes": size},
        "dataset": {
            "raw_rows": raw_rows, "valid_rows": len(candles), "invalid_rows": row_error_count,
            "symbols": symbols, "intervals": intervals,
            "first_timestamp": first_time.isoformat() if first_time else None,
            "last_timestamp": last_time.isoformat() if last_time else None,
            "timestamp_span_seconds": span_seconds,
            "flat_close_transition_ratio": round(flat_ratio, 6) if flat_ratio is not None else None,
        },
        "checks": {
            "required_columns_present": True, "duplicate_headers": [], "missing_headers": [],
            "file_size_within_limit": True, "max_file_bytes": max_file_bytes,
            "max_rows": max_rows, "duplicate_timestamps": duplicate_timestamps,
            "out_of_order_rows": out_of_order, "mixed_symbols_or_intervals": mixed,
            "future_timestamps": future_count, "gap_count": gap_count,
            "estimated_missing_candles": estimated_missing, "stale": stale,
            "stale_after_intervals": stale_after_intervals, "age_seconds": age_seconds,
            "unknown_interval": unknown_interval,
        },
        "gaps": gaps,
        "row_errors": row_errors,
        "row_error_count": row_error_count,
        "row_errors_truncated": row_error_count > len(row_errors),
        "warnings": warnings,
        "blocking_reasons": blocking,
        "readiness": {
            "research_allowed_by_health_gate": status == "READY",
            "live_execution_allowed": False,
            "recommendation": (
                "READY_FOR_OFFLINE_RESEARCH" if status == "READY" else
                "NO_DATA" if status == "NO_DATA" else
                "REVIEW_WARNINGS_BEFORE_RESEARCH" if status == "DEGRADED" else
                "REPAIR_SOURCE_DATA_BEFORE_RESEARCH"
            ),
        },
        "mode": "pre_ingestion_local_csv_audit",
        "orders_submitted": False,
        "trade_action": "NONE",
    }
    return report
