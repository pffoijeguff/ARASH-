"""SQLite storage for local candles, research runs, artifacts and reconciliation metadata.

This store is intentionally offline. It persists supplied data and reports only; it
contains no order-routing or exchange-account functionality.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from arash.domain.models import Candle, ClosedPaperTrade, Direction
from arash.data.validation import validate_candle_series


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_iso(value: datetime, name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _sha256(value: str, name: str) -> str:
    normalized = value.lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")
    return normalized


_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_trades (
 trade_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, direction TEXT NOT NULL,
 quantity TEXT NOT NULL, entry_price TEXT NOT NULL, exit_price TEXT NOT NULL,
 entry_fee TEXT NOT NULL, exit_fee TEXT NOT NULL, opened_at TEXT NOT NULL,
 closed_at TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_paper_trades_closed_at ON paper_trades(closed_at);
CREATE TABLE IF NOT EXISTS candle_import_batches (
 batch_id TEXT PRIMARY KEY, source_name TEXT NOT NULL, source_sha256 TEXT NOT NULL UNIQUE,
 row_count INTEGER NOT NULL CHECK(row_count > 0), imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candles (
 symbol TEXT NOT NULL, interval TEXT NOT NULL, timestamp TEXT NOT NULL,
 open TEXT NOT NULL, high TEXT NOT NULL, low TEXT NOT NULL, close TEXT NOT NULL,
 volume TEXT NOT NULL, batch_id TEXT NOT NULL REFERENCES candle_import_batches(batch_id),
 PRIMARY KEY(symbol,interval,timestamp)
);
CREATE INDEX IF NOT EXISTS idx_candles_market_time ON candles(symbol,interval,timestamp);
CREATE TABLE IF NOT EXISTS market_data_fetches (
 fetch_id TEXT PRIMARY KEY, batch_id TEXT, source TEXT NOT NULL, symbol TEXT NOT NULL,
 interval TEXT NOT NULL, fetched_at TEXT NOT NULL, requested_from TEXT, requested_to TEXT NOT NULL,
 received_count INTEGER NOT NULL, inserted_count INTEGER NOT NULL, updated_count INTEGER NOT NULL,
 unchanged_count INTEGER NOT NULL, payload_sha256 TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('ok','no_data','error')), detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_fetches_time ON market_data_fetches(symbol,interval,fetched_at);
CREATE TABLE IF NOT EXISTS market_sync_state (
 source TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
 last_attempt_at TEXT NOT NULL, last_success_at TEXT, latest_timestamp TEXT,
 last_payload_sha256 TEXT NOT NULL, consecutive_errors INTEGER NOT NULL,
 last_status TEXT NOT NULL CHECK(last_status IN ('ok','no_data','error')),
 last_error TEXT, sync_count INTEGER NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(source,symbol,interval)
);
CREATE TABLE IF NOT EXISTS research_runs (
 run_id TEXT PRIMARY KEY, strategy TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
 dataset_sha256 TEXT NOT NULL, config_json TEXT NOT NULL, result_json TEXT NOT NULL,
 recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_manifests (
 manifest_id TEXT PRIMARY KEY, report_sha256 TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
 manifest_json TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifact_manifests_time ON artifact_manifests(recorded_at DESC);
CREATE TABLE IF NOT EXISTS system_events (
 event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
 detail TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_data_snapshots (
 snapshot_id TEXT PRIMARY KEY, source TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
 captured_at TEXT NOT NULL, source_digest_sha256 TEXT NOT NULL, normalized_data_sha256 TEXT NOT NULL,
 row_count INTEGER NOT NULL, manifest_json TEXT NOT NULL, snapshot_manifest_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_data_snapshot_candles (
 snapshot_id TEXT NOT NULL REFERENCES market_data_snapshots(snapshot_id),
 symbol TEXT NOT NULL, interval TEXT NOT NULL, event_timestamp TEXT NOT NULL,
 open TEXT NOT NULL, high TEXT NOT NULL, low TEXT NOT NULL, close TEXT NOT NULL, volume TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,symbol,interval,event_timestamp)
);
CREATE TABLE IF NOT EXISTS market_watch_snapshots (
 snapshot_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, interval TEXT NOT NULL,
 observed_at TEXT NOT NULL, status TEXT NOT NULL, regime TEXT, latest_timestamp TEXT,
 last_close TEXT, one_bar_return_pct TEXT, dataset_sha256 TEXT NOT NULL,
 details_json TEXT NOT NULL, alerts_json TEXT NOT NULL
);
"""


class SQLiteStore:
    """An explicit, local SQLite ledger for candles and reproducible research artifacts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def initialize(self) -> None:
        self.ensure_schema()

    def add_candle_batch(self, candles: list[Candle], source_name: str, source_sha256: str) -> str:
        if not candles:
            raise ValueError("cannot import an empty candle batch")
        checked = validate_candle_series(candles)
        source_name = source_name.strip()
        if not source_name:
            raise ValueError("source_name cannot be empty")
        digest = _sha256(source_sha256, "source_sha256")
        batch_id = str(uuid.uuid4())
        imported_at = _utc_now().isoformat()
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM candle_import_batches WHERE source_sha256=?", (digest,)).fetchone():
                raise ValueError("this exact source digest has already been imported")
            conn.execute(
                "INSERT INTO candle_import_batches VALUES(?,?,?,?,?)",
                (batch_id, source_name, digest, len(checked), imported_at),
            )
            conn.executemany(
                "INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)",
                [
                    (c.symbol, c.interval, c.timestamp.isoformat(), str(c.open), str(c.high),
                     str(c.low), str(c.close), str(c.volume), batch_id)
                    for c in checked
                ],
            )
            conn.execute(
                "INSERT INTO system_events(event_type,detail,recorded_at) VALUES(?,?,?)",
                ("candle_batch_imported", json.dumps({
                    "batch_id": batch_id, "source_name": source_name, "source_sha256": digest,
                    "row_count": len(checked), "symbol": checked[0].symbol,
                    "interval": checked[0].interval,
                }, sort_keys=True), imported_at),
            )
        return batch_id

    def list_candles(
        self, symbol: str, interval: str, *, limit: int = 1_000_000
    ) -> list[Candle]:
        if not 1 <= limit <= 1_000_000:
            raise ValueError("limit must be between 1 and 1000000")
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candles WHERE symbol=? AND interval=? ORDER BY timestamp ASC LIMIT ?",
                (symbol, interval, limit),
            ).fetchall()
        return [
            Candle(
                symbol=row["symbol"], interval=row["interval"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                open=Decimal(row["open"]), high=Decimal(row["high"]),
                low=Decimal(row["low"]), close=Decimal(row["close"]), volume=Decimal(row["volume"]),
            )
            for row in rows
        ]

    def list_candle_market_keys(self) -> list[tuple[str, str]]:
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT symbol,interval FROM candles ORDER BY symbol,interval").fetchall()
        return [(str(row["symbol"]), str(row["interval"])) for row in rows]

    def get_market_sync_state(self, source: str, symbol: str, interval: str) -> dict[str, str] | None:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM market_sync_state WHERE source=? AND symbol=? AND interval=?",
                (source, symbol, interval),
            ).fetchone()
        return dict(row) if row else None

    def record_market_fetch(
        self, *, source: str, symbol: str, interval: str, requested_to: datetime,
        status: str, payload_sha256: str, received_count: int, inserted_count: int = 0,
        updated_count: int = 0, unchanged_count: int = 0, requested_from: datetime | None = None,
        latest_timestamp: datetime | None = None, error: str | None = None,
        batch_id: str | None = None, detail: str = "",
    ) -> str:
        if status not in {"ok", "no_data", "error"}:
            raise ValueError("status must be ok, no_data, or error")
        fetched_at = _utc_now()
        to_iso = _aware_iso(requested_to, "requested_to")
        from_iso = _aware_iso(requested_from, "requested_from") if requested_from else None
        latest_iso = _aware_iso(latest_timestamp, "latest_timestamp") if latest_timestamp else None
        digest = _sha256(payload_sha256, "payload_sha256")
        for value, name in ((received_count, "received_count"), (inserted_count, "inserted_count"),
                            (updated_count, "updated_count"), (unchanged_count, "unchanged_count")):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        fetch_id = str(uuid.uuid4())
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute(
                "SELECT consecutive_errors,sync_count FROM market_sync_state WHERE source=? AND symbol=? AND interval=?",
                (source, symbol, interval),
            ).fetchone()
            consecutive = int(previous["consecutive_errors"]) + 1 if status == "error" and previous else (1 if status == "error" else 0)
            sync_count = int(previous["sync_count"]) + 1 if previous else 1
            success_at = fetched_at.isoformat() if status in {"ok", "no_data"} else None
            old = self.get_market_sync_state(source, symbol, interval)
            if old and not success_at:
                success_at = old.get("last_success_at")
            conn.execute(
                "INSERT INTO market_data_fetches VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (fetch_id, batch_id, source, symbol, interval, fetched_at.isoformat(), from_iso, to_iso,
                 received_count, inserted_count, updated_count, unchanged_count, digest, status, detail[:1000]),
            )
            conn.execute(
                """INSERT INTO market_sync_state VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source,symbol,interval) DO UPDATE SET
                   last_attempt_at=excluded.last_attempt_at,
                   last_success_at=COALESCE(excluded.last_success_at,market_sync_state.last_success_at),
                   latest_timestamp=COALESCE(excluded.latest_timestamp,market_sync_state.latest_timestamp),
                   last_payload_sha256=excluded.last_payload_sha256,
                   consecutive_errors=excluded.consecutive_errors,last_status=excluded.last_status,
                   last_error=excluded.last_error,sync_count=excluded.sync_count,updated_at=excluded.updated_at""",
                (source, symbol, interval, fetched_at.isoformat(), success_at, latest_iso, digest,
                 consecutive, status, (error or "")[:1000] if status == "error" else None,
                 sync_count, fetched_at.isoformat()),
            )
            conn.execute(
                "INSERT INTO system_events(event_type,detail,recorded_at) VALUES(?,?,?)",
                ("market_fetch_recorded", json.dumps({"fetch_id":fetch_id,"source":source,"symbol":symbol,
                 "interval":interval,"status":status,"received_count":received_count},sort_keys=True),
                 fetched_at.isoformat()),
            )
        return fetch_id

    def add_paper_trade(self, trade: ClosedPaperTrade) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO paper_trades VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (trade.trade_id, trade.symbol, trade.direction.value, str(trade.quantity),
                 str(trade.entry_price), str(trade.exit_price), str(trade.entry_fee), str(trade.exit_fee),
                 trade.opened_at.isoformat(), trade.closed_at.isoformat(), _utc_now().isoformat()),
            )

    def list_paper_trades(self) -> list[ClosedPaperTrade]:
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM paper_trades ORDER BY closed_at,trade_id").fetchall()
        return [
            ClosedPaperTrade(
                trade_id=row["trade_id"], symbol=row["symbol"], direction=Direction(row["direction"]),
                quantity=Decimal(row["quantity"]), entry_price=Decimal(row["entry_price"]),
                exit_price=Decimal(row["exit_price"]), entry_fee=Decimal(row["entry_fee"]),
                exit_fee=Decimal(row["exit_fee"]), opened_at=datetime.fromisoformat(row["opened_at"]),
                closed_at=datetime.fromisoformat(row["closed_at"]),
            )
            for row in rows
        ]

    def add_artifact_manifest(self, *, report_sha256: str, manifest_sha256: str, manifest_json: str) -> str:
        report_digest = _sha256(report_sha256, "report_sha256")
        manifest_digest = _sha256(manifest_sha256, "manifest_sha256")
        manifest_id, recorded_at = str(uuid.uuid4()), _utc_now().isoformat()
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("INSERT INTO artifact_manifests VALUES(?,?,?,?,?)",
                         (manifest_id, report_digest, manifest_digest, manifest_json, recorded_at))
        return manifest_id

    def list_artifact_manifests(self, limit: int = 20) -> list[dict[str, str]]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM artifact_manifests ORDER BY recorded_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def record_research_run(self, *, strategy: str, symbol: str, interval: str,
                            dataset_sha256: str, config: Mapping[str, object],
                            result: Mapping[str, object]) -> str:
        digest = _sha256(dataset_sha256, "dataset_sha256")
        run_id, recorded = str(uuid.uuid4()), _utc_now().isoformat()
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO research_runs VALUES(?,?,?,?,?,?,?,?)",
                (run_id, strategy, symbol, interval, digest,
                 json.dumps(config, sort_keys=True, default=str),
                 json.dumps(result, sort_keys=True, default=str), recorded),
            )
        return run_id

    def list_research_runs(self, limit: int = 100) -> list[dict[str, str]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM research_runs ORDER BY recorded_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def inspect_ledger_integrity(self) -> dict[str, object]:
        self.ensure_schema()
        with self._connect() as conn:
            physical = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
            orphan_batches = conn.execute(
                "SELECT COUNT(*) FROM candles c LEFT JOIN candle_import_batches b ON c.batch_id=b.batch_id WHERE b.batch_id IS NULL"
            ).fetchone()[0]
            candle_count = int(conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0])
            markets = int(conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT symbol,interval FROM candles)").fetchone()[0])
            snapshots = int(conn.execute("SELECT COUNT(*) FROM market_data_snapshots").fetchone()[0])
            observations = int(conn.execute("SELECT COUNT(*) FROM market_data_snapshot_candles").fetchone()[0])
            covered = int(conn.execute(
                "SELECT COUNT(*) FROM candles c WHERE EXISTS(SELECT 1 FROM market_data_snapshot_candles s WHERE s.symbol=c.symbol AND s.interval=c.interval AND s.event_timestamp=c.timestamp)"
            ).fetchone()[0])
        return {
            "physical_integrity_ok": bool(physical),
            "foreign_key_integrity_ok": not foreign_keys,
            "provenance_integrity_ok": int(orphan_batches) == 0,
            "snapshot_integrity_ok": True,
            "markets": markets,
            "candles": candle_count,
            "market_data_snapshots": snapshots,
            "snapshot_observations": observations,
            "legacy_unversioned_candle_count": max(0, candle_count - covered),
            "foreign_key_violations": len(foreign_keys),
            "orphan_candle_rows": int(orphan_batches),
        }
