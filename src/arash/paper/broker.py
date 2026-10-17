"""Durable, offline-only simulated spot broker.

The broker has no network client and accepts only caller-supplied reference prices.
It never sends live orders. Requests are idempotent by account and client order ID.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

from arash.risk.engine import RiskInputs, RiskPolicy, assess_risk

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class PaperOrderResult:
    order_id: str
    client_order_id: str
    account_id: str
    symbol: str
    side: str
    quantity: Decimal
    reference_price: Decimal
    fill_price: Decimal | None
    fee: Decimal | None
    status: str
    rejection_reason: str | None
    requested_at: datetime
    filled_at: datetime | None
    base_currency: str = "UNSPECIFIED"
    quote_currency: str = "SIMULATED_UNITS"
    replayed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": "paper_simulation_only",
            "live_orders_submitted": False,
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "base_currency": self.base_currency,
            "quote_currency": self.quote_currency,
            "side": self.side,
            "quantity": str(self.quantity),
            "reference_price": str(self.reference_price),
            "fill_price": str(self.fill_price) if self.fill_price is not None else None,
            "fee": str(self.fee) if self.fee is not None else None,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "requested_at": self.requested_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "replayed_idempotently": self.replayed,
        }


@dataclass(frozen=True, slots=True)
class PaperAccountSnapshot:
    account_id: str
    account_currency: str
    cash: Decimal
    position_value: Decimal
    equity: Decimal
    initial_cash: Decimal
    net_pnl: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    positions: tuple[dict[str, str], ...]
    marks: dict[str, str]
    recorded_at: datetime
    snapshot_id: str | None = None
    mark_timestamps: dict[str, str] = field(default_factory=dict)
    max_mark_age_seconds: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": "paper_simulation_only",
            "live_orders_submitted": False,
            "account_id": self.account_id,
            "account_currency": self.account_currency,
            "monetary_values_currency": self.account_currency,
            "cash": str(self.cash),
            "position_value": str(self.position_value),
            "equity": str(self.equity),
            "initial_cash": str(self.initial_cash),
            "net_pnl": str(self.net_pnl),
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "positions": [dict(position) for position in self.positions],
            "marks": dict(self.marks),
            "mark_timestamps": dict(self.mark_timestamps),
            "recorded_at": self.recorded_at.isoformat(),
            "snapshot_id": self.snapshot_id,
            "fx_conversion_enabled": False,
        }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_accounts (
  account_id TEXT PRIMARY KEY, initial_cash TEXT NOT NULL, cash TEXT NOT NULL,
  realized_pnl TEXT NOT NULL DEFAULT '0', account_currency TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_instruments (
  symbol TEXT PRIMARY KEY, base_currency TEXT NOT NULL, quote_currency TEXT NOT NULL,
  metadata_source TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_positions (
  account_id TEXT NOT NULL REFERENCES paper_accounts(account_id), symbol TEXT NOT NULL,
  quantity TEXT NOT NULL, avg_entry_price TEXT NOT NULL, remaining_entry_fees TEXT NOT NULL,
  PRIMARY KEY(account_id, symbol)
);
CREATE TABLE IF NOT EXISTS paper_orders (
  order_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, client_order_id TEXT NOT NULL,
  request_sha256 TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
  quantity TEXT NOT NULL, reference_price TEXT NOT NULL, fill_price TEXT, fee TEXT,
  status TEXT NOT NULL, rejection_reason TEXT, requested_at TEXT NOT NULL, filled_at TEXT,
  base_currency TEXT NOT NULL, quote_currency TEXT NOT NULL,
  UNIQUE(account_id, client_order_id)
);
CREATE INDEX IF NOT EXISTS idx_paper_orders_time ON paper_orders(account_id, requested_at DESC);
CREATE TABLE IF NOT EXISTS paper_fills (
  fill_id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE, account_id TEXT NOT NULL,
  symbol TEXT NOT NULL, side TEXT NOT NULL, quantity TEXT NOT NULL, fill_price TEXT NOT NULL,
  fee TEXT NOT NULL, realized_pnl TEXT NOT NULL, filled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_equity_snapshots (
  snapshot_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, marks_json TEXT NOT NULL,
  mark_timestamps_json TEXT NOT NULL, cash TEXT NOT NULL, position_value TEXT NOT NULL,
  equity TEXT NOT NULL, initial_cash TEXT NOT NULL, net_pnl TEXT NOT NULL,
  realized_pnl TEXT NOT NULL, unrealized_pnl TEXT NOT NULL, recorded_at TEXT NOT NULL,
  account_currency TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_paper_snapshots_time ON paper_equity_snapshots(account_id, recorded_at DESC);
CREATE TABLE IF NOT EXISTS paper_risk_controls (
  account_id TEXT PRIMARY KEY, kill_switch_active INTEGER NOT NULL,
  reason TEXT, tripped_at TEXT, cleared_at TEXT, clear_reason TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
  event_type TEXT NOT NULL, details_json TEXT NOT NULL, recorded_at TEXT NOT NULL
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None, field_name: str) -> datetime:
    result = value or _now()
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return result.astimezone(timezone.utc)


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _symbol(value: str) -> str:
    result = _text(value, "symbol").upper()
    if len(result) > 64 or any(ch.isspace() for ch in result):
        raise ValueError("symbol must be a compact identifier without whitespace (max 64 chars)")
    return result


def _currency(value: str, name: str, allow_simulated: bool = False) -> str:
    result = _text(value, name).upper()
    if allow_simulated and result == "SIMULATED_UNITS":
        return result
    if not result.isascii() or not result.isalnum() or not 2 <= len(result) <= 12:
        raise ValueError(f"{name} must be an ASCII alphanumeric currency code (2-12 chars)")
    return result


def _decimal(value: Decimal | str | int, name: str, positive: bool = False) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a decimal-compatible finite value") from exc
    if not result.is_finite() or (positive and result <= ZERO):
        raise ValueError(f"{name} must be finite" + (" and greater than zero" if positive else ""))
    return result


def _event(conn: sqlite3.Connection, account_id: str, event: str, detail: dict[str, object], at: datetime) -> None:
    conn.execute(
        "INSERT INTO paper_events(account_id,event_type,details_json,recorded_at) VALUES(?,?,?,?)",
        (account_id, event, json.dumps(detail, sort_keys=True, separators=(",", ":")), at.isoformat()),
    )


class PaperBroker:
    """SQLite-backed long-only paper broker with idempotency and persistent risk halts."""

    def __init__(
        self, db_path: str | Path, *, fee_rate: Decimal = Decimal("0.001"),
        slippage_rate: Decimal = Decimal("0.0005"),
    ) -> None:
        self.path = Path(db_path)
        self.fee_rate = _decimal(fee_rate, "fee_rate")
        self.slippage_rate = _decimal(slippage_rate, "slippage_rate")
        if not ZERO <= self.fee_rate < ONE or not ZERO <= self.slippage_rate < ONE:
            raise ValueError("fee_rate and slippage_rate must be in [0, 1)")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def create_account(self, account_id: str, initial_cash: Decimal, *, account_currency: str = "SIMULATED_UNITS") -> None:
        account_id = _text(account_id, "account_id")
        initial_cash = _decimal(initial_cash, "initial_cash", positive=True)
        account_currency = _currency(account_currency, "account_currency", allow_simulated=True)
        self.initialize()
        at = _now()
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO paper_accounts(account_id,initial_cash,cash,realized_pnl,account_currency,created_at) VALUES(?,?,?,?,?,?)",
                    (account_id, str(initial_cash), str(initial_cash), "0", account_currency, at.isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"paper account {account_id!r} already exists; refusing to reset its balance") from exc
            _event(conn, account_id, "account_created", {
                "initial_cash": str(initial_cash), "account_currency": account_currency,
                "mode": "paper_simulation_only", "fx_conversion_enabled": False,
            }, at)

    def register_instrument(self, symbol: str, *, base_currency: str, quote_currency: str) -> dict[str, str]:
        symbol = _symbol(symbol)
        base = _currency(base_currency, "base_currency")
        quote = _currency(quote_currency, "quote_currency")
        if base == quote:
            raise ValueError("base_currency and quote_currency must differ")
        self.initialize()
        at = _now().isoformat()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM paper_instruments WHERE symbol=?", (symbol,)).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO paper_instruments VALUES(?,?,?,?,?,?)",
                    (symbol, base, quote, "explicit", at, at),
                )
            elif (row["base_currency"], row["quote_currency"]) != (base, quote):
                raise ValueError(f"instrument {symbol} already has a different currency contract")
            row = conn.execute("SELECT * FROM paper_instruments WHERE symbol=?", (symbol,)).fetchone()
            return dict(row)

    def list_instruments(self) -> list[dict[str, str]]:
        self.initialize()
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM paper_instruments ORDER BY symbol")]

    def _risk_control(self, conn: sqlite3.Connection, account_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM paper_risk_controls WHERE account_id=?", (account_id,)).fetchone()

    def submit_market_order(
        self, *, account_id: str, client_order_id: str, symbol: str, side: str,
        quantity: Decimal, reference_price: Decimal, requested_at: datetime | None = None,
        risk_policy: RiskPolicy | None = None, risk_stop_price: Decimal | None = None,
        risk_peak_equity: Decimal | None = None, risk_daily_start_equity: Decimal | None = None,
        risk_marks: Mapping[str, Decimal] | None = None,
    ) -> PaperOrderResult:
        account_id = _text(account_id, "account_id")
        client_order_id = _text(client_order_id, "client_order_id")
        symbol = _symbol(symbol)
        side = _text(side, "side").lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell; short selling is disabled")
        quantity = _decimal(quantity, "quantity", positive=True)
        reference_price = _decimal(reference_price, "reference_price", positive=True)
        requested = _aware(requested_at, "requested_at")
        marks = {_symbol(k): _decimal(v, f"mark[{k}]", positive=True) for k, v in (risk_marks or {}).items()}
        if len(marks) != len(risk_marks or {}):
            raise ValueError("duplicate risk marks after symbol normalization")
        if side == "buy" and risk_policy is None:
            # Fail closed: purchases must be accompanied by current, explicit risk inputs.
            rejection_for_missing_risk = True
        else:
            rejection_for_missing_risk = False
        if side == "buy" and risk_policy is not None:
            if risk_stop_price is None or risk_peak_equity is None or risk_daily_start_equity is None:
                raise ValueError("risk-gated buys require stop, peak-equity, and daily-start-equity inputs")
            risk_stop_price = _decimal(risk_stop_price, "risk_stop_price", positive=True)
            risk_peak_equity = _decimal(risk_peak_equity, "risk_peak_equity", positive=True)
            risk_daily_start_equity = _decimal(risk_daily_start_equity, "risk_daily_start_equity", positive=True)
            if risk_stop_price >= reference_price:
                raise ValueError("risk_stop_price must be below the reference price for long-only buys")
            if risk_policy.fee_rate < self.fee_rate or risk_policy.slippage_rate < self.slippage_rate:
                raise ValueError("risk policy costs must be at least as conservative as broker costs")

        risk_payload = None if risk_policy is None else {
            "policy": repr(risk_policy), "stop": str(risk_stop_price), "peak": str(risk_peak_equity),
            "daily_start": str(risk_daily_start_equity), "marks": {k: str(v) for k, v in sorted(marks.items())},
        }
        request_payload = {
            "account": account_id, "client_id": client_order_id, "symbol": symbol, "side": side,
            "quantity": str(quantity.normalize()), "reference_price": str(reference_price.normalize()),
            "fee_rate": str(self.fee_rate), "slippage_rate": str(self.slippage_rate), "risk": risk_payload,
        }
        fingerprint = hashlib.sha256(json.dumps(request_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.initialize()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            account = conn.execute("SELECT * FROM paper_accounts WHERE account_id=?", (account_id,)).fetchone()
            if account is None:
                raise ValueError(f"paper account {account_id!r} does not exist")
            prior = conn.execute(
                "SELECT * FROM paper_orders WHERE account_id=? AND client_order_id=?",
                (account_id, client_order_id),
            ).fetchone()
            if prior is not None:
                if prior["request_sha256"] != fingerprint:
                    raise ValueError("client_order_id was already used for a different request")
                return self._order_result(prior, replayed=True)

            instrument = conn.execute("SELECT * FROM paper_instruments WHERE symbol=?", (symbol,)).fetchone()
            if instrument is None and account["account_currency"] == "SIMULATED_UNITS":
                at = _now().isoformat()
                conn.execute(
                    "INSERT INTO paper_instruments VALUES(?,?,?,?,?,?)",
                    (symbol, "UNSPECIFIED", "SIMULATED_UNITS", "legacy_simulation_assumption", at, at),
                )
                instrument = conn.execute("SELECT * FROM paper_instruments WHERE symbol=?", (symbol,)).fetchone()
            if instrument is None:
                raise ValueError("instrument currency contract is missing; register it before ordering")
            base, quote = str(instrument["base_currency"]), str(instrument["quote_currency"])
            order_id = str(uuid.uuid4())
            fill_price = reference_price * (ONE + self.slippage_rate if side == "buy" else ONE - self.slippage_rate)
            notional = quantity * fill_price
            fee = notional * self.fee_rate
            reason = None
            if quote != account["account_currency"]:
                reason = "quote_currency_mismatch_fx_conversion_disabled"
            if rejection_for_missing_risk:
                reason = "mandatory_risk_gate_missing_buy_requires_risk_policy_and_stop"
            control = self._risk_control(conn, account_id)
            if control is not None and int(control["kill_switch_active"]) == 1:
                reason = "account_kill_switch_active:" + str(control["reason"] or "unspecified")

            pos = conn.execute("SELECT * FROM paper_positions WHERE account_id=? AND symbol=?", (account_id, symbol)).fetchone()
            cash = Decimal(account["cash"])
            if reason is None and side == "buy" and risk_policy is not None:
                current_exposure = ZERO
                same_symbol_exposure = ZERO
                positions = conn.execute("SELECT * FROM paper_positions WHERE account_id=? ORDER BY symbol", (account_id,)).fetchall()
                for held in positions:
                    held_symbol = str(held["symbol"])
                    mark = reference_price if held_symbol == symbol else marks.get(held_symbol)
                    if mark is None:
                        raise ValueError(f"risk-gated buy requires a mark for other open position {held_symbol}")
                    marked = Decimal(held["quantity"]) * mark
                    current_exposure += marked
                    if held_symbol == symbol:
                        same_symbol_exposure += marked
                equity = cash + current_exposure
                assessment = assess_risk(RiskInputs(
                    equity=equity, cash=cash, entry_price=reference_price, stop_price=risk_stop_price,
                    current_exposure=current_exposure, current_position_exposure=same_symbol_exposure,
                    daily_pnl=equity - risk_daily_start_equity, peak_equity=risk_peak_equity,
                    requested_quantity=quantity,
                ), risk_policy)
                if not assessment.allowed or assessment.requested_quantity_allowed is False:
                    reason = "risk_policy_blocked:" + ",".join(assessment.block_reasons)

            if reason is None and side == "buy" and notional + fee > cash:
                reason = "insufficient_simulated_cash_leverage_disabled"
            if reason is None and side == "sell":
                if pos is None:
                    reason = "no_open_long_position_short_selling_disabled"
                elif quantity > Decimal(pos["quantity"]):
                    reason = "sell_quantity_exceeds_open_position_short_selling_disabled"

            if reason is not None:
                conn.execute(
                    "INSERT INTO paper_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (order_id, account_id, client_order_id, fingerprint, symbol, side, str(quantity),
                     str(reference_price), None, None, "REJECTED", reason, requested.isoformat(), None, base, quote),
                )
                _event(conn, account_id, "order_rejected", {
                    "order_id": order_id, "client_order_id": client_order_id, "reason": reason,
                }, requested)
                row = conn.execute("SELECT * FROM paper_orders WHERE order_id=?", (order_id,)).fetchone()
                return self._order_result(row)

            realized = ZERO
            if side == "buy":
                new_cash = cash - notional - fee
                if pos is None:
                    conn.execute(
                        "INSERT INTO paper_positions VALUES(?,?,?,?,?)",
                        (account_id, symbol, str(quantity), str(fill_price), str(fee)),
                    )
                else:
                    old_q = Decimal(pos["quantity"])
                    new_q = old_q + quantity
                    avg = (old_q * Decimal(pos["avg_entry_price"]) + quantity * fill_price) / new_q
                    fee_balance = Decimal(pos["remaining_entry_fees"]) + fee
                    conn.execute(
                        "UPDATE paper_positions SET quantity=?,avg_entry_price=?,remaining_entry_fees=? WHERE account_id=? AND symbol=?",
                        (str(new_q), str(avg), str(fee_balance), account_id, symbol),
                    )
            else:
                old_q = Decimal(pos["quantity"])
                avg = Decimal(pos["avg_entry_price"])
                old_fee = Decimal(pos["remaining_entry_fees"])
                allocated = old_fee * quantity / old_q
                new_cash = cash + notional - fee
                realized = (fill_price - avg) * quantity - allocated - fee
                remaining = old_q - quantity
                if remaining == ZERO:
                    conn.execute("DELETE FROM paper_positions WHERE account_id=? AND symbol=?", (account_id, symbol))
                else:
                    conn.execute(
                        "UPDATE paper_positions SET quantity=?,remaining_entry_fees=? WHERE account_id=? AND symbol=?",
                        (str(remaining), str(old_fee - allocated), account_id, symbol),
                    )
                conn.execute(
                    "UPDATE paper_accounts SET realized_pnl=? WHERE account_id=?",
                    (str(Decimal(account["realized_pnl"]) + realized), account_id),
                )
            conn.execute("UPDATE paper_accounts SET cash=? WHERE account_id=?", (str(new_cash), account_id))
            filled = requested.isoformat()
            conn.execute(
                "INSERT INTO paper_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (order_id, account_id, client_order_id, fingerprint, symbol, side, str(quantity),
                 str(reference_price), str(fill_price), str(fee), "FILLED", None,
                 requested.isoformat(), filled, base, quote),
            )
            conn.execute(
                "INSERT INTO paper_fills VALUES(?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), order_id, account_id, symbol, side, str(quantity), str(fill_price),
                 str(fee), str(realized), filled),
            )
            _event(conn, account_id, "order_filled", {
                "order_id": order_id, "client_order_id": client_order_id, "symbol": symbol,
                "side": side, "quantity": str(quantity), "reference_price": str(reference_price),
                "fill_price": str(fill_price), "fee": str(fee), "realized_pnl": str(realized),
            }, requested)
            row = conn.execute("SELECT * FROM paper_orders WHERE order_id=?", (order_id,)).fetchone()
            return self._order_result(row)

    @staticmethod
    def _order_result(row: sqlite3.Row, replayed: bool = False) -> PaperOrderResult:
        return PaperOrderResult(
            order_id=row["order_id"], client_order_id=row["client_order_id"], account_id=row["account_id"],
            symbol=row["symbol"], side=row["side"], quantity=Decimal(row["quantity"]),
            reference_price=Decimal(row["reference_price"]),
            fill_price=Decimal(row["fill_price"]) if row["fill_price"] is not None else None,
            fee=Decimal(row["fee"]) if row["fee"] is not None else None,
            status=row["status"], rejection_reason=row["rejection_reason"],
            requested_at=datetime.fromisoformat(row["requested_at"]),
            filled_at=datetime.fromisoformat(row["filled_at"]) if row["filled_at"] else None,
            base_currency=row["base_currency"], quote_currency=row["quote_currency"], replayed=replayed,
        )

    def account_snapshot(
        self, account_id: str, marks: Mapping[str, Decimal] | None = None, *,
        recorded_at: datetime | None = None, persist: bool = False,
        mark_timestamps: Mapping[str, datetime | str] | None = None,
        max_mark_age_seconds: int | None = None,
    ) -> PaperAccountSnapshot:
        account_id = _text(account_id, "account_id")
        at = _aware(recorded_at, "recorded_at")
        normalized_marks = {_symbol(k): _decimal(v, f"mark[{k}]", positive=True) for k, v in (marks or {}).items()}
        if max_mark_age_seconds is not None and (
            not isinstance(max_mark_age_seconds, int) or isinstance(max_mark_age_seconds, bool)
            or not 1 <= max_mark_age_seconds <= 604800
        ):
            raise ValueError("max_mark_age_seconds must be an integer between 1 and 604800")
        mark_times: dict[str, datetime] = {}
        for raw_symbol, raw_time in (mark_timestamps or {}).items():
            symbol = _symbol(raw_symbol)
            if symbol not in normalized_marks:
                raise ValueError(f"mark timestamp supplied without price for {symbol}")
            timestamp = datetime.fromisoformat(raw_time.replace("Z", "+00:00")) if isinstance(raw_time, str) else raw_time
            timestamp = _aware(timestamp, f"mark_timestamp[{symbol}]")
            if timestamp > at:
                raise ValueError(f"mark timestamp for {symbol} is after snapshot time")
            mark_times[symbol] = timestamp
        self.initialize()
        with self._connect() as conn:
            if persist:
                conn.execute("BEGIN IMMEDIATE")
            account = conn.execute("SELECT * FROM paper_accounts WHERE account_id=?", (account_id,)).fetchone()
            if account is None:
                raise ValueError(f"paper account {account_id!r} does not exist")
            rows = conn.execute("SELECT * FROM paper_positions WHERE account_id=? ORDER BY symbol", (account_id,)).fetchall()
            required = [row["symbol"] for row in rows if row["symbol"] not in normalized_marks]
            if required:
                raise ValueError("a mark price is required for every open position: " + ", ".join(required))
            if max_mark_age_seconds is not None:
                missing = [row["symbol"] for row in rows if row["symbol"] not in mark_times]
                if missing:
                    raise ValueError("freshness enforcement requires mark timestamps: " + ", ".join(missing))
                stale = [symbol for symbol in mark_times if (at - mark_times[symbol]).total_seconds() > max_mark_age_seconds]
                if stale:
                    raise ValueError("stale marks exceed freshness limit: " + ", ".join(stale))
            cash = Decimal(account["cash"])
            initial_cash = Decimal(account["initial_cash"])
            position_value = ZERO
            unrealized = ZERO
            payload: list[dict[str, str]] = []
            for row in rows:
                symbol = str(row["symbol"])
                instrument = conn.execute("SELECT * FROM paper_instruments WHERE symbol=?", (symbol,)).fetchone()
                if instrument is None or instrument["quote_currency"] != account["account_currency"]:
                    raise ValueError(f"position {symbol} has no compatible currency contract; FX conversion is disabled")
                quantity = Decimal(row["quantity"])
                average = Decimal(row["avg_entry_price"])
                entry_fees = Decimal(row["remaining_entry_fees"])
                mark = normalized_marks[symbol]
                value = quantity * mark
                pnl = (mark - average) * quantity - entry_fees
                position_value += value
                unrealized += pnl
                payload.append({
                    "symbol": symbol, "base_currency": instrument["base_currency"],
                    "quote_currency": instrument["quote_currency"], "market_value_currency": account["account_currency"],
                    "quantity": str(quantity), "avg_entry_price": str(average),
                    "remaining_entry_fees": str(entry_fees), "mark_price": str(mark),
                    "market_value": str(value), "unrealized_pnl_net_of_entry_fees": str(pnl),
                })
            equity = cash + position_value
            realized = Decimal(account["realized_pnl"])
            snapshot_id = str(uuid.uuid4()) if persist else None
            snapshot = PaperAccountSnapshot(
                account_id=account_id, account_currency=account["account_currency"], cash=cash,
                position_value=position_value, equity=equity, initial_cash=initial_cash,
                net_pnl=equity-initial_cash, realized_pnl=realized, unrealized_pnl=unrealized,
                positions=tuple(payload), marks={k:str(v) for k,v in sorted(normalized_marks.items())},
                recorded_at=at, snapshot_id=snapshot_id,
                mark_timestamps={k:v.isoformat() for k,v in sorted(mark_times.items())},
                max_mark_age_seconds=max_mark_age_seconds,
            )
            if persist:
                conn.execute(
                    "INSERT INTO paper_equity_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (snapshot_id, account_id, json.dumps(snapshot.marks, sort_keys=True),
                     json.dumps(snapshot.mark_timestamps, sort_keys=True), str(cash), str(position_value),
                     str(equity), str(initial_cash), str(snapshot.net_pnl), str(realized), str(unrealized),
                     at.isoformat(), account["account_currency"]),
                )
                _event(conn, account_id, "equity_snapshot_recorded",
                       {"snapshot_id": snapshot_id, "equity": str(equity)}, at)
            return snapshot

    def list_orders(self, account_id: str, *, limit: int = 100) -> list[PaperOrderResult]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM paper_orders WHERE account_id=? ORDER BY requested_at DESC,order_id DESC LIMIT ?", (account_id, limit)).fetchall()
        return [self._order_result(row) for row in rows]

    def list_risk_snapshots(self, account_id: str) -> list[dict[str, str]]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute("SELECT equity,recorded_at FROM paper_equity_snapshots WHERE account_id=? ORDER BY recorded_at,snapshot_id", (account_id,)).fetchall()
        return [{"equity": row["equity"], "recorded_at": row["recorded_at"]} for row in rows]

    def list_snapshots(self, account_id: str, *, limit: int = 100) -> list[dict[str, str]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM paper_equity_snapshots WHERE account_id=? ORDER BY recorded_at DESC,snapshot_id DESC LIMIT ?", (account_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def get_kill_switch(self, account_id: str) -> dict[str, object]:
        self.initialize()
        with self._connect() as conn:
            account = conn.execute("SELECT account_id FROM paper_accounts WHERE account_id=?", (account_id,)).fetchone()
            if account is None:
                raise ValueError(f"paper account {account_id!r} does not exist")
            row = conn.execute("SELECT * FROM paper_risk_controls WHERE account_id=?", (account_id,)).fetchone()
        if row is None:
            return {"account_id": account_id, "active": False, "reason": None, "tripped_at": None, "cleared_at": None, "clear_reason": None}
        return {"account_id": account_id, "active": bool(row["kill_switch_active"]), "reason": row["reason"],
                "tripped_at": row["tripped_at"], "cleared_at": row["cleared_at"], "clear_reason": row["clear_reason"]}

    def trip_kill_switch(self, account_id: str, reason: str, *, at: datetime | None = None) -> dict[str, object]:
        account_id, reason = _text(account_id, "account_id"), _text(reason, "reason")
        recorded = _aware(at, "at")
        self.initialize()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM paper_accounts WHERE account_id=?", (account_id,)).fetchone() is None:
                raise ValueError(f"paper account {account_id!r} does not exist")
            current = conn.execute("SELECT * FROM paper_risk_controls WHERE account_id=?", (account_id,)).fetchone()
            if current is None:
                conn.execute("INSERT INTO paper_risk_controls VALUES(?,?,?,?,?,?,?)",
                             (account_id, 1, reason, recorded.isoformat(), None, None, recorded.isoformat()))
            elif not current["kill_switch_active"]:
                conn.execute("UPDATE paper_risk_controls SET kill_switch_active=1,reason=?,tripped_at=?,cleared_at=NULL,clear_reason=NULL,updated_at=? WHERE account_id=?",
                             (reason, recorded.isoformat(), recorded.isoformat(), account_id))
            _event(conn, account_id, "risk_kill_switch_tripped", {"reason": reason}, recorded)
        return self.get_kill_switch(account_id)

    def reset_kill_switch(self, account_id: str, reason: str, *, confirm: bool = False, at: datetime | None = None) -> dict[str, object]:
        account_id, reason = _text(account_id, "account_id"), _text(reason, "reason")
        if not confirm:
            raise ValueError("kill-switch reset requires explicit confirm=True")
        recorded = _aware(at, "at")
        self.initialize()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT kill_switch_active FROM paper_risk_controls WHERE account_id=?", (account_id,)).fetchone()
            if row is None or not row["kill_switch_active"]:
                raise ValueError("kill switch is not active; refusing a meaningless reset")
            conn.execute("UPDATE paper_risk_controls SET kill_switch_active=0,cleared_at=?,clear_reason=?,updated_at=? WHERE account_id=?",
                         (recorded.isoformat(), reason, recorded.isoformat(), account_id))
            _event(conn, account_id, "risk_kill_switch_manually_cleared", {"reason": reason, "explicit_confirmation": True}, recorded)
        return self.get_kill_switch(account_id)

