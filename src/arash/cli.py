"""Command-line interface for research-driven quantitative trading intelligence and risk analysis."""

from __future__ import annotations

import asyncio
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
from arash.data.streaming import stream_public_orderbook
from arash.data.reconcile import reconcile_market_data
from arash.storage.sqlite_store import SQLiteStore
from arash.paper.execution import ExecutionPolicy, simulate_execution
from arash.paper.execution_batch import simulate_execution_batch
from arash.paper.execution_stress import run_execution_stress_suite
from arash.risk.engine import RiskInputs, RiskPolicy, assess_risk
from arash.commands.paper import handle_paper_command
from arash.research.backtest import BacktestConfig, run_backtest
from arash.research.evaluation import evaluate_chronological_holdout
from arash.research.intelligence import build_market_intelligence
from arash.research.lab import run_experiment_grid
from arash.research.manifest import build_research_manifest
from arash.research.watch import state_from_market_report, evaluate_state_change
from arash.research.portfolio import summarize_backtests
from arash.research.quant_audit import audit_backtest_result
from arash.research.regimes import analyze_market_regimes
from arash.research.robustness import run_parameter_perturbations, run_chronological_subperiods
from arash.research.selection_bias import audit_candidate_family
from arash.research.pbo import estimate_probability_of_backtest_overfitting
from arash.research.pipeline import run_research_pipeline


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
            "ARASH: research-driven quantitative trading intelligence, market-data diagnostics, "
            "risk assessment and execution simulation. Production order routing is not available in this development branch."
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

    market_stream = commands.add_parser("market-stream", help="Stream public live order-book snapshots without trading permissions")
    market_stream.add_argument("--symbol", required=True, help="Market symbol, for example BTCIRT")
    market_stream.add_argument("--max-events", type=int, default=0, help="Stop after this many snapshots; 0 streams until interrupted")
    market_stream.add_argument("--max-reconnects", type=int, default=5, help="Maximum consecutive reconnect attempts")

    sync_market = commands.add_parser("market-sync", help="Fetch public OHLCV candles and persist a provenance snapshot locally")
    sync_market.add_argument("--db", required=True)
    sync_market.add_argument("--provider", default="nobitex-public-udf", choices=["nobitex-public-udf"])
    sync_market.add_argument("--symbol", required=True)
    sync_market.add_argument("--interval", required=True)
    sync_market.add_argument("--count", type=int, default=100)
    sync_market.add_argument("--to", type=_aware_timestamp, help="Upper bound as ISO-8601; defaults to current UTC")
    sync_market.add_argument("--timeout-seconds", type=float, default=8.0)
    sync_market.add_argument("--output")

    reconcile = commands.add_parser("market-reconcile", help="Reconcile local candle lineage and market snapshot metadata")
    reconcile.add_argument("--db", required=True)
    reconcile.add_argument("--output")

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

    batch = commands.add_parser("execution-batch", help="Run independent simulations for a bounded order list")
    batch.add_argument("path", help="OHLCV CSV data file")
    batch.add_argument("orders_json", help="JSON object containing an orders array")
    batch.add_argument("--fee-rate", type=_decimal, default=Decimal("0.001"))
    batch.add_argument("--slippage-rate", type=_decimal, default=Decimal("0.0005"))
    batch.add_argument("--spread-rate", type=_decimal, default=Decimal("0.001"))
    batch.add_argument("--market-impact-rate", type=_decimal, default=Decimal("0.002"))
    batch.add_argument("--max-participation-rate", type=_decimal, default=Decimal("0.10"))
    batch.add_argument("--max-bars", type=int, default=20)
    batch.add_argument("--max-orders", type=int, default=100)
    batch.add_argument("--output")

    manifest_parser = commands.add_parser("research-manifest", help="Generate a SHA-256 provenance manifest for a JSON report")
    manifest_parser.add_argument("path")
    manifest_parser.add_argument("--output")

    def add_backtest_options(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("path")
        command_parser.add_argument("--strategy", choices=["buy-hold", "sma-crossover"], default="buy-hold")
        command_parser.add_argument("--initial-cash", type=_decimal, default=Decimal("10000"))
        command_parser.add_argument("--position-fraction", type=_decimal, default=Decimal("0.10"))
        command_parser.add_argument("--fee-rate", type=_decimal, default=Decimal("0.001"))
        command_parser.add_argument("--slippage-rate", type=_decimal, default=Decimal("0.0005"))
        command_parser.add_argument("--spread-rate", type=_decimal, default=Decimal("0"))
        command_parser.add_argument("--market-impact-rate", type=_decimal, default=Decimal("0"))
        command_parser.add_argument("--short-window", type=int, default=5)
        command_parser.add_argument("--long-window", type=int, default=20)
        command_parser.add_argument("--liquidity-warning-threshold", type=_decimal, default=Decimal("0.10"))
        command_parser.add_argument("--output")
    backtest = commands.add_parser("backtest", help="Run an offline buy-hold or SMA baseline backtest")
    add_backtest_options(backtest)
    evaluate = commands.add_parser("evaluate", help="Run a chronological fixed-parameter holdout evaluation")
    add_backtest_options(evaluate)
    evaluate.add_argument("--train-fraction", type=_decimal, default=Decimal("0.70"))
    audit = commands.add_parser("quant-audit", help="Audit a baseline backtest's accounting and trade metrics")
    add_backtest_options(audit)
    robust = commands.add_parser("robustness", help="Run predeclared cost and position-size sensitivity scenarios")
    add_backtest_options(robust)
    robust.add_argument("--fee-multipliers", type=_decimal, nargs="+", default=[Decimal("1"),Decimal("1.5"),Decimal("2")])
    robust.add_argument("--slippage-multipliers", type=_decimal, nargs="+", default=[Decimal("1"),Decimal("2")])
    robust.add_argument("--subperiods", type=int, default=4)
    regimes = commands.add_parser("regime-analysis", help="Describe prior-only market regimes from OHLCV")
    regimes.add_argument("path")
    regimes.add_argument("--lookback", type=int, default=20)
    regimes.add_argument("--trend-threshold-pct", type=_decimal, default=Decimal("2.0"))
    regimes.add_argument("--high-volatility-threshold-pct", type=_decimal, default=Decimal("1.0"))
    regimes.add_argument("--output")
    intelligence = commands.add_parser("market-intelligence", help="Build a descriptive OHLCV intelligence report")
    intelligence.add_argument("path")
    intelligence.add_argument("--rsi-period", type=int, default=14)
    intelligence.add_argument("--atr-period", type=int, default=14)
    intelligence.add_argument("--volume-lookback", type=int, default=20)
    intelligence.add_argument("--regime-lookback", type=int, default=20)
    intelligence.add_argument("--output")
    pipeline = commands.add_parser("research-pipeline", help="Run CSV health gate and offline baseline backtest")
    pipeline.add_argument("path")
    pipeline.add_argument("--strategy", choices=["buy-hold", "sma-crossover"], default="buy-hold")
    pipeline.add_argument("--output", required=True, help="Write the JSON report to this path")

    grid = commands.add_parser("research-grid", help="Run a bounded experiment grid without selecting a winner")
    grid.add_argument("path")
    grid.add_argument("--strategies", nargs="+", choices=["buy-hold", "sma-crossover"], default=["buy-hold","sma-crossover"])
    grid.add_argument("--short-windows", type=int, nargs="+", default=[5])
    grid.add_argument("--long-windows", type=int, nargs="+", default=[20])
    grid.add_argument("--position-fractions", type=_decimal, nargs="+", default=[Decimal("0.10")])
    grid.add_argument("--max-candidates", type=int, default=100)
    grid.add_argument("--output")

    selection = commands.add_parser("selection-bias-audit", help="Summarize candidate-family selection-bias risk")
    selection.add_argument("--returns-pct", type=_decimal, nargs="+", required=True)
    selection.add_argument("--declared-candidate-count", type=int)
    selection.add_argument("--output")

    pbo = commands.add_parser("pbo-audit", help="Estimate backtest selection instability with CSCV")
    pbo.add_argument("path", help="JSON file containing aligned candidate_returns arrays")
    pbo.add_argument("--blocks", type=int, default=8, help="Even number of contiguous CSCV blocks (4-14)")
    pbo.add_argument("--output")

    paper_create = commands.add_parser("paper-account-create", help="Create a local simulated paper account")
    paper_create.add_argument("--db", required=True)
    paper_create.add_argument("--account-id", required=True)
    paper_create.add_argument("--initial-cash", type=_decimal, required=True)
    paper_create.add_argument("--account-currency", default="SIMULATED_UNITS")

    paper_register = commands.add_parser("paper-instrument-register", help="Register an explicit instrument currency contract")
    paper_register.add_argument("--db", required=True)
    paper_register.add_argument("--symbol", required=True)
    paper_register.add_argument("--base-currency", required=True)
    paper_register.add_argument("--quote-currency", required=True)
    paper_instruments = commands.add_parser("paper-instruments", help="List registered paper instrument currency contracts")
    paper_instruments.add_argument("--db", required=True)

    market_watch = commands.add_parser("market-watch", help="Compare a current market report with a previous report")
    market_watch.add_argument("current_report")
    market_watch.add_argument("--previous-report")
    market_watch.add_argument("--price-move-threshold-pct", type=_decimal, default=Decimal("5.0"))
    market_watch.add_argument("--output")

    paper_order = commands.add_parser("paper-order", help="Record a risk-gated local simulated spot order")
    paper_order.add_argument("--db", required=True)
    paper_order.add_argument("--account-id", required=True)
    paper_order.add_argument("--client-order-id", required=True)
    paper_order.add_argument("--symbol", required=True)
    paper_order.add_argument("--side", choices=["buy","sell"], required=True)
    paper_order.add_argument("--quantity", type=_decimal, required=True)
    paper_order.add_argument("--reference-price", type=_decimal, required=True)
    paper_order.add_argument("--at")
    paper_order.add_argument("--stop-price", type=_decimal)
    paper_order.add_argument("--peak-equity", type=_decimal)
    paper_order.add_argument("--daily-start-equity", type=_decimal)
    paper_order.add_argument("--risk-enabled", action="store_true", help="Legacy compatibility flag; explicit risk values remain mandatory.")
    paper_order.add_argument("--risk-per-trade-pct", type=_decimal, default=Decimal("1"))
    paper_order.add_argument("--max-position-pct", type=_decimal, default=Decimal("20"))
    paper_order.add_argument("--max-portfolio-exposure-pct", type=_decimal, default=Decimal("60"))
    paper_order.add_argument("--max-daily-loss-pct", type=_decimal, default=Decimal("3"))
    paper_order.add_argument("--max-drawdown-pct", type=_decimal, default=Decimal("10"))
    paper_order.add_argument("--fee-rate", type=_decimal, default=Decimal("0.001"))
    paper_order.add_argument("--slippage-rate", type=_decimal, default=Decimal("0.0005"))
    paper_order.add_argument("--mark", action="append", nargs=2, metavar=("SYMBOL","PRICE"), default=[])
    paper_status = commands.add_parser("paper-status", help="Value an offline paper account using explicit marks")
    paper_status.add_argument("--db", required=True)
    paper_status.add_argument("--account-id", required=True)
    paper_status.add_argument("--mark", action="append", nargs=2, metavar=("SYMBOL","PRICE"), default=[])
    paper_status.add_argument("--at")
    paper_status.add_argument("--record", action="store_true")
    for command_name, help_text in [
        ("paper-history","List local simulated paper orders"),
        ("paper-snapshots","List persisted local paper-account snapshots"),
    ]:
        item=commands.add_parser(command_name,help=help_text)
        item.add_argument("--db",required=True)
        item.add_argument("--account-id",required=True)
        item.add_argument("--limit",type=int,default=100)
    paper_risk = commands.add_parser("paper-risk-audit", help="Audit a persisted paper account against explicit risk limits")
    paper_risk.add_argument("--db",required=True)
    paper_risk.add_argument("--account-id",required=True)
    paper_risk.add_argument("--mark",action="append",nargs=2,default=[])
    paper_risk.add_argument("--mark-at",action="append",nargs=2,default=[])
    paper_risk.add_argument("--at")
    paper_risk.add_argument("--max-mark-age-seconds",type=int,default=3600)
    paper_risk.add_argument("--max-daily-loss-pct",type=_decimal,default=Decimal("3"))
    paper_risk.add_argument("--max-drawdown-pct",type=_decimal,default=Decimal("10"))
    paper_risk.add_argument("--max-position-pct",type=_decimal,default=Decimal("20"))
    paper_risk.add_argument("--max-portfolio-exposure-pct",type=_decimal,default=Decimal("60"))
    paper_risk.add_argument("--risk-day-timezone",default="UTC")
    paper_risk.add_argument("--output")
    paper_stress = commands.add_parser("paper-risk-stress",help="Run deterministic hypothetical paper-portfolio stress scenarios")
    paper_stress.add_argument("--db",required=True)
    paper_stress.add_argument("--account-id",required=True)
    paper_stress.add_argument("--mark",action="append",nargs=2,default=[])
    paper_stress.add_argument("--mark-at",action="append",nargs=2,default=[])
    paper_stress.add_argument("--at")
    paper_stress.add_argument("--max-mark-age-seconds",type=int,default=3600)
    paper_stress.add_argument("--max-daily-loss-pct",type=_decimal,default=Decimal("3"))
    paper_stress.add_argument("--max-drawdown-pct",type=_decimal,default=Decimal("10"))
    paper_stress.add_argument("--max-position-pct",type=_decimal,default=Decimal("20"))
    paper_stress.add_argument("--max-portfolio-exposure-pct",type=_decimal,default=Decimal("60"))
    paper_stress.add_argument("--risk-day-timezone",default="UTC")
    paper_stress.add_argument("--output")
    paper_reset = commands.add_parser("paper-risk-reset",help="Manually clear an active paper-account kill switch")
    paper_reset.add_argument("--db",required=True)
    paper_reset.add_argument("--account-id",required=True)
    paper_reset.add_argument("--reason",required=True)
    paper_reset.add_argument("--confirm-reset",action="store_true")
    paper_reset.add_argument("--at")

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

        if args.command in {"market-fetch", "market-sync"}:
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
                "mode": "read_only_public_market_data" if args.command == "market-fetch" else "read_only_market_fetch_with_local_snapshot",
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
            if args.command == "market-sync":
                store = SQLiteStore(args.db)
                if result.candles:
                    persistence = store.persist_market_snapshot(
                        source=result.source,
                        symbol=result.symbol,
                        interval=result.interval,
                        candles=result.candles,
                        source_digest_sha256=result.payload_sha256,
                        requested_to=result.requested_to,
                        captured_at=result.fetched_at,
                    )
                    report["persistence"] = persistence
                else:
                    fetch_id = store.record_market_fetch(
                        source=result.source,
                        symbol=result.symbol,
                        interval=result.interval,
                        requested_to=result.requested_to,
                        status="no_data",
                        payload_sha256=result.payload_sha256,
                        received_count=0,
                        detail="The public provider returned no candles for the requested window.",
                    )
                    report["persistence"] = {"fetch_id": fetch_id, "status": "no_data", "snapshot_created": False}
            _print_json(report, args.output)
            return 0 if result.candles else 2

        if args.command == "market-stream":
            if args.max_events < 0:
                raise ValueError("--max-events must be zero or a positive integer")
            event_count = 0
            stop_event = asyncio.Event()

            async def emit_snapshot(snapshot: Any) -> None:
                nonlocal event_count
                _print_json(snapshot.to_dict())
                event_count += 1
                if args.max_events and event_count >= args.max_events:
                    stop_event.set()

            try:
                asyncio.run(stream_public_orderbook(
                    args.symbol,
                    emit_snapshot,
                    stop_event=stop_event,
                    max_reconnects=args.max_reconnects,
                ))
            except KeyboardInterrupt:
                print("Market stream stopped by user.", file=sys.stderr)
                return 130
            _print_json({
                "stream_status": "STOPPED",
                "symbol": args.symbol.upper(),
                "snapshots_received": event_count,
                "read_only_public_market_data": True,
                "orders_submitted": False,
            })
            return 0

        if args.command == "market-reconcile":
            result = reconcile_market_data(SQLiteStore(args.db))
            _print_json(result, args.output)
            return 0 if result.get("status") == "READY" else 1

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

        if args.command == "research-manifest":
            result = build_research_manifest(args.path)
            _print_json(result, args.output)
            return 0

        if args.command == "execution-batch":
            report_path = Path(args.orders_json)
            if not report_path.is_file() or report_path.stat().st_size > 2_000_000:
                raise ValueError("orders JSON must be an existing file no larger than 2 MB")
            orders_payload = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(orders_payload, dict) or not isinstance(orders_payload.get("orders"), list):
                raise ValueError("orders JSON must be an object with an 'orders' array")
            candles = load_candles_csv(args.path)
            batch_policy = ExecutionPolicy(
                fee_rate=args.fee_rate,
                slippage_rate=args.slippage_rate,
                spread_rate=args.spread_rate,
                market_impact_rate=args.market_impact_rate,
                max_participation_rate=args.max_participation_rate,
                max_bars=args.max_bars,
            )
            result = simulate_execution_batch(
                candles, orders_payload["orders"], policy=batch_policy, max_orders=args.max_orders
            )
            _print_json(result, args.output)
            return 0

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

        if args.command in {"backtest", "evaluate", "quant-audit", "robustness"}:
            candles = load_candles_csv(args.path)
            config = BacktestConfig(
                initial_cash=args.initial_cash,
                position_fraction=args.position_fraction,
                fee_rate=args.fee_rate,
                slippage_rate=args.slippage_rate,
                spread_rate=args.spread_rate,
                market_impact_rate=args.market_impact_rate,
                liquidity_warning_threshold=args.liquidity_warning_threshold,
                short_window=args.short_window,
                long_window=args.long_window,
            )
            if args.command == "backtest":
                result = run_backtest(candles, strategy=args.strategy, config=config)
                _print_json(result.to_dict(include_trades=True, include_equity_curve=True), args.output)
                return 0
            if args.command == "evaluate":
                result = evaluate_chronological_holdout(
                    candles, strategy=args.strategy, config=config, train_fraction=args.train_fraction
                )
                _print_json(result.to_dict(), args.output)
                return 0
            if args.command == "quant-audit":
                result = run_backtest(candles, strategy=args.strategy, config=config)
                _print_json({"backtest": result.to_dict(include_trades=False), "audit": audit_backtest_result(result)}, args.output)
                return 0
            results = run_parameter_perturbations(
                candles, strategy=args.strategy, base_config=config,
                fee_multipliers=args.fee_multipliers,
                slippage_multipliers=args.slippage_multipliers,
            )
            results["chronological_subperiods"] = run_chronological_subperiods(
                candles, strategy=args.strategy, config=config, segments=args.subperiods
            )
            _print_json(results, args.output)
            return 0

        if args.command == "regime-analysis":
            result = analyze_market_regimes(
                load_candles_csv(args.path), lookback=args.lookback,
                trend_threshold_pct=args.trend_threshold_pct,
                high_volatility_threshold_pct=args.high_volatility_threshold_pct,
            )
            _print_json(result, args.output)
            return 0

        if args.command == "market-intelligence":
            result = build_market_intelligence(
                load_candles_csv(args.path), rsi_period=args.rsi_period,
                atr_period=args.atr_period, volume_lookback=args.volume_lookback,
                regime_lookback=args.regime_lookback,
            )
            _print_json(result, args.output)
            return 0

        if args.command == "research-pipeline":
            result = run_research_pipeline(args.path, strategy=args.strategy, output_path=args.output)
            _print_json(result)
            return 0 if result.get("status") == "COMPLETED_OFFLINE_SIMULATION" else 1

        if args.command == "research-grid":
            result = run_experiment_grid(
                load_candles_csv(args.path), strategies=args.strategies,
                short_windows=args.short_windows, long_windows=args.long_windows,
                position_fractions=args.position_fractions, max_candidates=args.max_candidates,
            )
            _print_json(result, args.output)
            return 0

        if args.command == "selection-bias-audit":
            result = audit_candidate_family(args.returns_pct, declared_candidate_count=args.declared_candidate_count)
            _print_json(result, args.output)
            return 0

        if args.command == "pbo-audit":
            report_path = Path(args.path)
            if not report_path.is_file() or report_path.stat().st_size > 5_000_000:
                raise ValueError("PBO input must be an existing JSON file no larger than 5 MB")
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("candidate_returns"), dict):
                raise ValueError("PBO input must be a JSON object with a candidate_returns object")
            result = estimate_probability_of_backtest_overfitting(
                payload["candidate_returns"], blocks=args.blocks
            )
            result["input_path"] = str(report_path)
            _print_json(result, args.output)
            return 0

        if args.command == "market-watch":
            def read_report(path: str) -> dict[str, Any]:
                report_path = Path(path)
                if not report_path.is_file() or report_path.stat().st_size > 2_000_000:
                    raise ValueError("market report must be an existing file smaller than 2 MB")
                payload = json.loads(report_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("market report must be a JSON object")
                return payload
            current_report = read_report(args.current_report)
            current_state = state_from_market_report(current_report)
            previous_state = state_from_market_report(read_report(args.previous_report)) if args.previous_report else None
            alerts = evaluate_state_change(
                current_state, previous_state,
                price_move_threshold_pct=args.price_move_threshold_pct,
            )
            _print_json({
                "schema_version": 1,
                "mode": "market_state_change_diagnostics",
                "current_state": current_state,
                "previous_state": previous_state,
                "alerts": alerts,
                "trade_action": "NONE",
                "execution_enabled": False,
                "note": "Alerts report observable data/regime changes only; they are not trade signals.",
            }, args.output)
            return 0

        if args.command in {
            "paper-account-create","paper-instrument-register","paper-instruments","paper-order","paper-status",
            "paper-history","paper-snapshots","paper-risk-audit","paper-risk-stress","paper-risk-reset"
        }:
            return int(handle_paper_command(args) or 0)

        parser.error(f"unsupported command: {args.command}")
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"arash: error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
