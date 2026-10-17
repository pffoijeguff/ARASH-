"""Command-line interface for offline data quality, read-only market data and risk analysis."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from arash import __version__
from arash.data.csv_loader import load_candles_csv
from arash.data.health import audit_csv_health
from arash.data.connectors import CandleRequest, default_connector_registry
from arash.paper.execution import ExecutionPolicy, simulate_execution
from arash.paper.execution_stress import run_execution_stress_suite
from arash.risk.engine import RiskInputs, RiskPolicy, assess_risk


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise argparse.ArgumentTypeError("value must be a decimal number") from exc
    if not result.is_finite():
        raise argparse.ArgumentTypeError("value must be finite")
    return result


def _aware_timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timestamp must be ISO-8601") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone (for example, trailing Z)")
    return result.astimezone(timezone.utc)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError(f"Cannot serialize type {type(value).__name__}")


def _print_json(payload: object, output: str | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n"
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"Report written to {path}")
    print(text, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arash",
        description=(
            "ARASH Foundation: offline quantitative research, data quality, risk diagnostics "
            "and simulated execution. No live order-submission command is supported."
        ),
    )
    parser.add_argument("--version", action="version", version=f"ARASH Foundation {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    health = commands.add_parser("csv-health", help="Audit an OHLCV CSV before research")
    health.add_argument("path")
    health.add_argument("--at", type=_aware_timestamp, help="Reference time as ISO-8601")
    health.add_argument("--stale-after-intervals", type=int, default=2)
    health.add_argument("--max-file-bytes", type=int, default=50_000_000)
    health.add_argument("--max-rows", type=int, default=1_000_000)
    health.add_argument("--output")

    validate = commands.add_parser("csv-validate", help="Load and strictly validate OHLCV CSV rows")
    validate.add_argument("path")
    validate.add_argument("--output")

    market = commands.add_parser("market-fetch", help="Fetch public read-only OHLCV data")
    market.add_argument("--provider", default="nobitex-public-udf", choices=["nobitex-public-udf"])
    market.add_argument("--symbol", required=True)
    market.add_argument("--interval", required=True)
    market.add_argument("--count", type=int, default=100)
    market.add_argument("--to", type=_aware_timestamp, help="Upper bound as ISO-8601; defaults to current UTC")
    market.add_argument("--timeout-seconds", type=float, default=8.0)
    market.add_argument("--output")

    risk = commands.add_parser("risk-check", help="Calculate a hypothetical long-only position size")
    risk.add_argument("--equity", required=True, type=_decimal)
    risk.add_argument("--cash", required=True, type=_decimal)
    risk.add_argument("--entry-price", required=True, type=_decimal)
    risk.add_argument("--stop-price", required=True, type=_decimal)
    risk.add_argument("--current-exposure", type=_decimal, default=Decimal("0"))
    risk.add_argument("--current-position-exposure", type=_decimal, default=Decimal("0"))
    risk.add_argument("--daily-pnl", type=_decimal, default=Decimal("0"))
    risk.add_argument("--peak-equity", type=_decimal)
    risk.add_argument("--requested-quantity", type=_decimal)
    risk.add_argument("--risk-per-trade-pct", type=_decimal, default=Decimal("1"))
    risk.add_argument("--max-position-pct", type=_decimal, default=Decimal("20"))
    risk.add_argument("--max-portfolio-exposure-pct", type=_decimal, default=Decimal("60"))
    risk.add_argument("--max-daily-loss-pct", type=_decimal, default=Decimal("3"))
    risk.add_argument("--max-drawdown-pct", type=_decimal, default=Decimal("10"))
    risk.add_argument("--fee-rate", type=_decimal, default=Decimal("0.001"))
    risk.add_argument("--slippage-rate", type=_decimal, default=Decimal("0.0005"))
    risk.add_argument("--output")

    execution = commands.add_parser("execution-simulate", help="Simulate a bounded candle-based execution")
    execution.add_argument("path", help="CSV containing timezone-aware OHLCV rows")
    execution.add_argument("--side", choices=["buy", "sell"], required=True)
    execution.add_argument("--quantity", type=_decimal, required=True)
    execution.add_argument("--submitted-at", type=_aware_timestamp, required=True)
    execution.add_argument("--order-type", choices=["market", "limit"], default="market")
    execution.add_argument("--limit-price", type=_decimal)
    execution.add_argument("--fee-rate", type=_decimal, default=Decimal("0.001"))
    execution.add_argument("--slippage-rate", type=_decimal, default=Decimal("0.0005"))
    execution.add_argument("--spread-rate", type=_decimal, default=Decimal("0.001"))
    execution.add_argument("--market-impact-rate", type=_decimal, default=Decimal("0.002"))
    execution.add_argument("--max-participation-rate", type=_decimal, default=Decimal("0.10"))
    execution.add_argument("--max-bars", type=int, default=20)
    execution.add_argument("--output")

    stress = commands.add_parser("execution-stress", help="Compare explicit execution-cost sensitivity scenarios")
    stress.add_argument("path", help="CSV containing timezone-aware OHLCV rows")
    stress.add_argument("--side", choices=["buy", "sell"], required=True)
    stress.add_argument("--quantity", type=_decimal, required=True)
    stress.add_argument("--submitted-at", type=_aware_timestamp, required=True)
    stress.add_argument("--order-type", choices=["market", "limit"], default="market")
    stress.add_argument("--limit-price", type=_decimal)
    stress.add_argument("--fee-rate", type=_decimal, default=Decimal("0.001"))
    stress.add_argument("--slippage-rate", type=_decimal, default=Decimal("0.0005"))
    stress.add_argument("--spread-rate", type=_decimal, default=Decimal("0.001"))
    stress.add_argument("--market-impact-rate", type=_decimal, default=Decimal("0.002"))
    stress.add_argument("--max-participation-rate", type=_decimal, default=Decimal("0.10"))
    stress.add_argument("--max-bars", type=int, default=20)
    stress.add_argument("--output")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "csv-health":
            report = audit_csv_health(
                args.path,
                now=args.at,
                stale_after_intervals=args.stale_after_intervals,
                max_file_bytes=args.max_file_bytes,
                max_rows=args.max_rows,
            )
            _print_json(report, args.output)
            return 0 if report["status"] == "READY" else 1

        if args.command == "csv-validate":
            candles = load_candles_csv(args.path)
            report = {
                "mode": "offline_csv_validation",
                "status": "PASS",
                "live_orders_submitted": False,
                "path": str(Path(args.path)),
                "candle_count": len(candles),
                "symbol": candles[0].symbol,
                "interval": candles[0].interval,
                "first_timestamp": candles[0].timestamp,
                "last_timestamp": candles[-1].timestamp,
            }
            _print_json(report, args.output)
            return 0

        if args.command == "market-fetch":
            requested_to = args.to or datetime.now(timezone.utc)
            registry = default_connector_registry()
            connector = registry.resolve(args.provider)
            result = connector.fetch(CandleRequest(
                symbol=args.symbol,
                interval=args.interval,
                count=args.count,
                timeout_seconds=args.timeout_seconds,
                requested_to=requested_to,
            ))
            report = {
                "mode": "read_only_public_market_data",
                "live_orders_submitted": False,
                "source": result.source,
                "symbol": result.symbol,
                "interval": result.interval,
                "requested_to": result.requested_to,
                "fetched_at": result.fetched_at,
                "candle_count": len(result.candles),
                "payload_sha256": result.payload_sha256,
                "candles": [
                    {
                        "timestamp": candle.timestamp,
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": candle.volume,
                    }
                    for candle in result.candles
                ],
                "note": "Public market-data retrieval only; no account credentials or order endpoints are used.",
            }
            _print_json(report, args.output)
            return 0 if result.candles else 2

        if args.command == "risk-check":
            percent_names = (
                "risk_per_trade_pct", "max_position_pct", "max_portfolio_exposure_pct",
                "max_daily_loss_pct", "max_drawdown_pct",
            )
            for name in percent_names:
                value = getattr(args, name)
                if not Decimal("0") < value <= Decimal("100"):
                    raise ValueError(f"--{name.replace('_', '-')} must be greater than 0 and at most 100")
            policy = RiskPolicy(
                risk_per_trade=args.risk_per_trade_pct / Decimal("100"),
                max_position_fraction=args.max_position_pct / Decimal("100"),
                max_portfolio_exposure_fraction=args.max_portfolio_exposure_pct / Decimal("100"),
                max_daily_loss_fraction=args.max_daily_loss_pct / Decimal("100"),
                max_drawdown_fraction=args.max_drawdown_pct / Decimal("100"),
                fee_rate=args.fee_rate,
                slippage_rate=args.slippage_rate,
            )
            assessment = assess_risk(RiskInputs(
                equity=args.equity,
                cash=args.cash,
                entry_price=args.entry_price,
                stop_price=args.stop_price,
                current_exposure=args.current_exposure,
                current_position_exposure=args.current_position_exposure,
                daily_pnl=args.daily_pnl,
                peak_equity=args.peak_equity,
                requested_quantity=args.requested_quantity,
            ), policy)
            _print_json(assessment.to_dict(), args.output)
            return 0 if assessment.allowed else 1

        if args.command in {"execution-simulate", "execution-stress"}:
            candles = load_candles_csv(args.path)
            policy = ExecutionPolicy(
                fee_rate=args.fee_rate,
                slippage_rate=args.slippage_rate,
                spread_rate=args.spread_rate,
                market_impact_rate=args.market_impact_rate,
                max_participation_rate=args.max_participation_rate,
                max_bars=args.max_bars,
            )
            if args.command == "execution-simulate":
                result = simulate_execution(
                    candles,
                    side=args.side,
                    quantity=args.quantity,
                    submitted_at=args.submitted_at,
                    order_type=args.order_type,
                    limit_price=args.limit_price,
                    policy=policy,
                )
                _print_json(result.to_dict(), args.output)
                return 0 if result.status == "FILLED" else 1
            result = run_execution_stress_suite(
                candles,
                side=args.side,
                quantity=args.quantity,
                submitted_at=args.submitted_at,
                order_type=args.order_type,
                limit_price=args.limit_price,
                base_policy=policy,
            )
            _print_json(result, args.output)
            return 0

        parser.error(f"unsupported command: {args.command}")
    except (OSError, ValueError, KeyError) as exc:
        print(f"arash: error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
