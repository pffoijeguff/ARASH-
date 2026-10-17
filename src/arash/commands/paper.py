"""Paper-account command handlers separated from CLI parsing and research commands."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from arash.paper.broker import PaperBroker
from arash.risk.engine import RiskPolicy
from arash.risk.monitor import audit_portfolio_risk
from arash.risk.stress import build_portfolio_stress_report

PAPER_COMMANDS = frozenset({
    "paper-risk-audit", "paper-risk-stress", "paper-risk-reset", "paper-account-create",
    "paper-instrument-register", "paper-instruments", "paper-order", "paper-status", "paper-history", "paper-snapshots",
})


def _now_arg(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("--at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--at must include timezone, e.g. +03:30 or Z")
    return parsed


def _write_json(path_value: str | None, payload: dict[str, Any]) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"JSON report: {path.resolve()}")


def handle_paper_command(args: Any) -> int | None:
    """Run a paper-domain command, returning None when this module does not own it."""
    if args.command not in PAPER_COMMANDS:
        return None

    if args.command == "paper-risk-audit":
        at_value = _now_arg(args.at)
        marks = dict(args.mark)
        mark_timestamps = dict(args.mark_at)
        if len(marks) != len(args.mark):
            raise ValueError("a symbol may only have one --mark value")
        if len(mark_timestamps) != len(args.mark_at):
            raise ValueError("a symbol may only have one --mark-at value")
        if not 1 <= args.max_mark_age_seconds <= 604800:
            raise ValueError("--max-mark-age-seconds must be an integer between 1 and 604800")
        pct_names = ("max_daily_loss_pct", "max_drawdown_pct", "max_position_pct", "max_portfolio_exposure_pct")
        for name in pct_names:
            value = getattr(args, name)
            if value <= 0 or value > 100:
                raise ValueError(f"--{name.replace('_', '-')} must be greater than 0 and at most 100")
        broker = PaperBroker(args.db)
        at_value = at_value or datetime.now(timezone.utc)
        snapshot = broker.account_snapshot(
            args.account_id, marks, recorded_at=at_value, persist=True,
            mark_timestamps=mark_timestamps,
            max_mark_age_seconds=args.max_mark_age_seconds,
        )
        history = broker.list_risk_snapshots(args.account_id)
        policy = RiskPolicy(
            max_daily_loss_fraction=args.max_daily_loss_pct / Decimal("100"),
            max_drawdown_fraction=args.max_drawdown_pct / Decimal("100"),
            max_position_fraction=args.max_position_pct / Decimal("100"),
            max_portfolio_exposure_fraction=args.max_portfolio_exposure_pct / Decimal("100"),
        )
        audit = audit_portfolio_risk(snapshot, history, policy=policy, risk_day_timezone=args.risk_day_timezone)
        if audit.block_reasons:
            broker.trip_kill_switch(args.account_id, ";".join(audit.block_reasons), at=audit.evaluated_at)
        control = broker.get_kill_switch(args.account_id)
        payload = audit.to_dict()
        payload["kill_switch"] = control
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if args.output:
            _write_json(args.output, payload)
        if audit.block_reasons:
            print("Circuit breaker tripped. New paper orders are blocked until an explicit manual reset.", file=sys.stderr)
            return 1
        if control["active"]:
            print("Account remains halted; this audit does not automatically clear an existing kill switch.", file=sys.stderr)
            return 1
        return 0

    if args.command == "paper-risk-stress":
        at_value = _now_arg(args.at) or datetime.now(timezone.utc)
        marks = dict(args.mark)
        mark_timestamps = dict(args.mark_at)
        if len(marks) != len(args.mark):
            raise ValueError("a symbol may only have one --mark value")
        if len(mark_timestamps) != len(args.mark_at):
            raise ValueError("a symbol may only have one --mark-at value")
        if not 1 <= args.max_mark_age_seconds <= 604800:
            raise ValueError("--max-mark-age-seconds must be an integer between 1 and 604800")
        pct_names = ("max_daily_loss_pct", "max_drawdown_pct", "max_position_pct", "max_portfolio_exposure_pct")
        for name in pct_names:
            value = getattr(args, name)
            if value <= 0 or value > 100:
                raise ValueError(f"--{name.replace('_', '-')} must be greater than 0 and at most 100")
        broker = PaperBroker(args.db)
        snapshot = broker.account_snapshot(
            args.account_id, marks, recorded_at=at_value, persist=False,
            mark_timestamps=mark_timestamps,
            max_mark_age_seconds=args.max_mark_age_seconds,
        )
        history = broker.list_risk_snapshots(args.account_id)
        policy = RiskPolicy(
            max_daily_loss_fraction=args.max_daily_loss_pct / Decimal("100"),
            max_drawdown_fraction=args.max_drawdown_pct / Decimal("100"),
            max_position_fraction=args.max_position_pct / Decimal("100"),
            max_portfolio_exposure_fraction=args.max_portfolio_exposure_pct / Decimal("100"),
        )
        payload = build_portfolio_stress_report(snapshot, history, policy=policy, risk_day_timezone=args.risk_day_timezone)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        _write_json(args.output, payload)
        if payload["status"] in ("BASELINE_BLOCKED", "STRESS_BREACH"):
            print(
                "Stress limits breached under at least one tested scenario. This diagnostic does not mutate the account or kill switch.",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.command == "paper-risk-reset":
        at_value = _now_arg(args.at)
        broker = PaperBroker(args.db)
        state = broker.reset_kill_switch(
            args.account_id, args.reason, confirm=args.confirm_reset, at=at_value,
        )
        print(json.dumps({"mode": "paper_simulation_only", "risk_control": state}, ensure_ascii=False, indent=2))
        print("Manual reset recorded; ensure the root cause and current exposure have been reviewed.")
        return 0

    if args.command == "paper-account-create":
        broker = PaperBroker(args.db)
        broker.create_account(
            args.account_id, args.initial_cash, account_currency=args.account_currency
        )
        print(f"ARASH | PAPER ACCOUNT CREATED | {args.account_id}")
        print(f"Initial simulated cash: {args.initial_cash} {args.account_currency.upper()}")
        print(f"Account valuation currency: {args.account_currency.upper()}")
        print("FX conversion: DISABLED | no real funds, market feed, or exchange access")
        print("Mode: offline paper simulation only")
        return 0

    if args.command == "paper-instrument-register":
        broker = PaperBroker(args.db)
        instrument = broker.register_instrument(
            args.symbol, base_currency=args.base_currency, quote_currency=args.quote_currency
        )
        print(json.dumps({
            "mode": "paper_simulation_only",
            "instrument": instrument,
            "contract": "quantity is in base_currency; prices and notional are in quote_currency",
            "fx_conversion_enabled": False,
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.command == "paper-instruments":
        broker = PaperBroker(args.db)
        print(json.dumps({
            "mode": "paper_simulation_only",
            "fx_conversion_enabled": False,
            "instruments": broker.list_instruments(),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.command == "paper-order":
        at_value = _now_arg(args.at)
        broker = PaperBroker(args.db, fee_rate=args.fee_rate, slippage_rate=args.slippage_rate)
        risk_policy = None
        risk_stop = args.stop_price
        risk_peak = args.peak_equity
        risk_daily_start = args.daily_start_equity
        risk_marks = dict(args.mark)
        if len(risk_marks) != len(args.mark):
            raise ValueError("a symbol may only have one --mark value")
        if args.side == "buy" and all(
            value is not None for value in (args.stop_price, args.peak_equity, args.daily_start_equity)
        ):
            for name in (
                "risk_per_trade_pct", "max_position_pct", "max_portfolio_exposure_pct",
                "max_daily_loss_pct", "max_drawdown_pct",
            ):
                value = getattr(args, name)
                if value <= 0 or value > 100:
                    raise ValueError(f"--{name.replace('_', '-')} must be greater than 0 and at most 100")
            risk_policy = RiskPolicy(
                risk_per_trade=args.risk_per_trade_pct / Decimal("100"),
                max_position_fraction=args.max_position_pct / Decimal("100"),
                max_portfolio_exposure_fraction=args.max_portfolio_exposure_pct / Decimal("100"),
                max_daily_loss_fraction=args.max_daily_loss_pct / Decimal("100"),
                max_drawdown_fraction=args.max_drawdown_pct / Decimal("100"),
                fee_rate=args.fee_rate,
                slippage_rate=args.slippage_rate,
            )
        elif args.side == "buy":
            print(
                "BUY rejected unless --stop-price, --peak-equity, and --daily-start-equity are supplied; "
                "--risk-enabled is retained only for command compatibility.",
                file=sys.stderr,
            )
        result = broker.submit_market_order(
            account_id=args.account_id,
            client_order_id=args.client_order_id,
            symbol=args.symbol,
            side=args.side,
            quantity=args.quantity,
            reference_price=args.reference_price,
            requested_at=at_value,
            risk_policy=risk_policy,
            risk_stop_price=risk_stop,
            risk_peak_equity=risk_peak,
            risk_daily_start_equity=risk_daily_start,
            risk_marks=risk_marks,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        if result.status == "REJECTED":
            print("Risk guard rejected this simulated order; balances were not changed.", file=sys.stderr)
            return 1
        return 0

    if args.command == "paper-status":
        at_value = _now_arg(args.at)
        marks = dict(args.mark)
        if len(marks) != len(args.mark):
            raise ValueError("a symbol may only have one --mark value")
        broker = PaperBroker(args.db)
        snapshot = broker.account_snapshot(
            args.account_id, marks, recorded_at=at_value, persist=args.record
        )
        print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        print("Valuation uses caller-supplied marks; this command does not fetch market prices.")
        return 0

    if args.command == "paper-history":
        broker = PaperBroker(args.db)
        orders = broker.list_orders(args.account_id, limit=args.limit)
        if not orders:
            print("No simulated orders recorded for this account.")
            return 0
        for order in orders:
            print(
                f"{order.requested_at.isoformat()} | {order.status} | {order.side.upper()} "
                f"{order.quantity} {order.base_currency} {order.symbol} @ "
                f"{order.fill_price or order.reference_price} {order.quote_currency} "
                f"| client_id={order.client_order_id} | order_id={order.order_id}"
                + (f" | reason={order.rejection_reason}" if order.rejection_reason else "")
            )
        print("Mode: local paper simulation only; no exchange connection or live order capability")
        return 0

    if args.command == "paper-snapshots":
        broker = PaperBroker(args.db)
        snapshots = broker.list_snapshots(args.account_id, limit=args.limit)
        if not snapshots:
            print("No persisted equity snapshots recorded for this account.")
            return 0
        for snapshot in snapshots:
            print(
                f"{snapshot['recorded_at']} | equity={snapshot['equity']} {snapshot['account_currency']} "
                f"net_pnl={snapshot['net_pnl']} realized={snapshot['realized_pnl']} "
                f"unrealized={snapshot['unrealized_pnl']} | snapshot_id={snapshot['snapshot_id']}"
            )
        print("Historical marks are those explicitly supplied when each snapshot was recorded.")
        return 0

    return None
