from __future__ import annotations

import argparse
import base64
import hashlib
import io
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PARTS_DIR = REPO / ".recovery"
PART_GLOB = "reference.zip.b64.part*"
EXPECTED_PARTS = 46
EXPECTED_ENCODED_CHARS = 366_328
EXPECTED_ARCHIVE_SHA256 = "679f5a597857fe59a3e34ccd4b832058b7234d999171c74b660c46d7357bad3f"


def archive_payload() -> tuple[bool, str, bytes | None]:
    parts = sorted(PARTS_DIR.glob(PART_GLOB))
    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    if len(parts) != EXPECTED_PARTS or len(encoded) != EXPECTED_ENCODED_CHARS:
        return False, f"Archive incomplete: {len(parts)}/{EXPECTED_PARTS} chunks, {len(encoded)}/{EXPECTED_ENCODED_CHARS} characters.", None
    try:
        payload = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        return False, f"Archive base64 is invalid: {exc}", None
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_ARCHIVE_SHA256:
        return False, f"Archive checksum mismatch: {digest}", None
    return True, "Reference archive is complete and checksum-verified.", payload


def add_cli_integrations(cli_path: Path) -> None:
    cli = cli_path.read_text(encoding="utf-8")
    if "stream_public_market_data" not in cli:
        cli = cli.replace("import argparse\n", "import argparse\nimport asyncio\n", 1)
        import_anchor = "from arash import __version__\n"
        if import_anchor not in cli:
            raise SystemExit("Reference CLI import anchor was not found.")
        additions = (
            "from arash.data.streaming import OrderBookSnapshot, PublicTrade, stream_public_market_data\n"
            "from arash.research.streaming_features import StreamingMicrostructureFeatures\n"
            "from arash.research.pbo import estimate_probability_of_backtest_overfitting\n"
            "from arash.research.return_statistics import bootstrap_return_statistics\n"
        )
        cli = cli.replace(import_anchor, import_anchor + additions, 1)

    parser_anchor = "    args = parser.parse_args(argv)\n"
    if 'subparsers.add_parser("pbo-audit"' not in cli:
        parser_additions = """    pbo_parser = subparsers.add_parser("pbo-audit", help="Estimate backtest-selection instability with CSCV/PBO")
    pbo_parser.add_argument("path", help="JSON file containing candidate_returns")
    pbo_parser.add_argument("--blocks", type=int, default=8)
    pbo_parser.add_argument("--output")

    stats_parser = subparsers.add_parser("return-stats", help="Estimate block-bootstrap return-statistic uncertainty")
    stats_parser.add_argument("path", help="JSON file containing returns")
    stats_parser.add_argument("--iterations", type=int, default=2000)
    stats_parser.add_argument("--block-length", type=int, default=5)
    stats_parser.add_argument("--confidence-level", type=float, default=0.95)
    stats_parser.add_argument("--seed", type=int, default=0)
    stats_parser.add_argument("--periods-per-year", type=int)
    stats_parser.add_argument("--output")

    stream_parser = subparsers.add_parser("market-stream", help="Stream public order-book and trade data with rolling microstructure features")
    stream_parser.add_argument("--symbol", required=True, help="Market symbol, for example BTCIRT")
    stream_parser.add_argument("--max-events", type=int, default=0, help="Stop after this many events; 0 streams until interrupted")
    stream_parser.add_argument("--max-reconnects", type=int, default=5)
    stream_parser.add_argument("--depth-levels", type=int, default=10)
    stream_parser.add_argument("--flow-window-seconds", type=int, default=60)

"""
        if cli.count(parser_anchor) != 1:
            raise SystemExit("Reference CLI parser insertion anchor was not unique.")
        cli = cli.replace(parser_anchor, parser_additions + parser_anchor, 1)

    handler_anchor = "    try:\n        store = _store_from_args(args)\n"
    if 'if args.command == "return-stats":' not in cli:
        handler = """    try:
        if args.command == "pbo-audit":
            input_path = Path(args.path)
            if not input_path.is_file() or input_path.stat().st_size > 5_000_000:
                raise ValueError("PBO input must be an existing JSON file no larger than 5 MB")
            raw_input = input_path.read_bytes()
            payload = json.loads(raw_input)
            if not isinstance(payload, dict) or not isinstance(payload.get("candidate_returns"), dict):
                raise ValueError("PBO input must be a JSON object with a candidate_returns object")
            report = estimate_probability_of_backtest_overfitting(
                payload["candidate_returns"], blocks=args.blocks
            )
            report["input_sha256"] = hashlib.sha256(raw_input).hexdigest()
            rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
            print(rendered, end="")
            return 0

        if args.command == "return-stats":
            input_path = Path(args.path)
            if not input_path.is_file() or input_path.stat().st_size > 5_000_000:
                raise ValueError("return-statistics input must be an existing JSON file no larger than 5 MB")
            raw_input = input_path.read_bytes()
            payload = json.loads(raw_input)
            if not isinstance(payload, dict) or not isinstance(payload.get("returns"), list):
                raise ValueError("return-statistics input must be a JSON object with a returns array")
            report = bootstrap_return_statistics(
                payload["returns"], iterations=args.iterations, block_length=args.block_length,
                confidence_level=args.confidence_level, seed=args.seed,
                periods_per_year=args.periods_per_year,
            )
            report["input_sha256"] = hashlib.sha256(raw_input).hexdigest()
            rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
            print(rendered, end="")
            return 0

        if args.command == "market-stream":
            if args.max_events < 0:
                raise ValueError("--max-events must be zero or a positive integer")
            if not 1 <= args.depth_levels <= 500:
                raise ValueError("--depth-levels must be between 1 and 500")
            if not 5 <= args.flow_window_seconds <= 3600:
                raise ValueError("--flow-window-seconds must be between 5 and 3600")
            features = StreamingMicrostructureFeatures(
                window_seconds=args.flow_window_seconds, depth_limit=args.depth_levels
            )
            stop_event = asyncio.Event()
            event_count = 0

            async def emit(event: OrderBookSnapshot | PublicTrade) -> None:
                nonlocal event_count
                payload = features.observe(event)
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str), flush=True)
                event_count += 1
                if args.max_events and event_count >= args.max_events:
                    stop_event.set()

            asyncio.run(stream_public_market_data(
                args.symbol, emit, on_trade=emit, stop_event=stop_event,
                max_reconnects=args.max_reconnects,
            ))
            return 0

        store = _store_from_args(args)
"""
        if handler_anchor not in cli:
            raise SystemExit("Reference CLI dispatch anchor was not found.")
        cli = cli.replace(handler_anchor, handler, 1)

    cli = cli.replace(
        "except (OSError, ValueError, sqlite3.Error, ArithmeticError) as exc:",
        "except (OSError, ValueError, RuntimeError, sqlite3.Error, ArithmeticError) as exc:",
    )
    cli_path.write_text(cli, encoding="utf-8")


def restore() -> None:
    complete, message, payload = archive_payload()
    print(message, flush=True)
    if not complete or payload is None:
        raise SystemExit(1)

    with tempfile.TemporaryDirectory(prefix="arash-reference-restore-") as temporary:
        temp = Path(temporary)
        unpacked = temp / "unpacked"
        unpacked.mkdir()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for info in archive.infolist():
                destination = (unpacked / info.filename).resolve()
                if unpacked.resolve() not in destination.parents and destination != unpacked.resolve():
                    raise SystemExit(f"Unsafe archive path detected: {info.filename}")
            archive.extractall(unpacked)

        reference = unpacked / "ARASH_Foundation_28.0.0"
        required = ("src/arash/cli.py", "tests/test_paper_broker.py", "pyproject.toml", "scripts/release_gate.py")
        for relative in required:
            if not (reference / relative).is_file():
                raise SystemExit(f"Reference archive lacks required file: {relative}")

        addon_root = temp / "addons"
        addon_root.mkdir()
        addon_paths = (
            "src/arash/data/streaming.py",
            "src/arash/research/pbo.py",
            "src/arash/research/return_statistics.py",
            "src/arash/research/streaming_features.py",
            "tests/test_public_market_stream.py",
            "tests/test_research_diagnostics.py",
            "sample_data/pbo_demo_candidate_returns.json",
            "sample_data/return_stats_demo.json",
        )
        for relative in addon_paths:
            source = REPO / relative
            if not source.is_file():
                raise SystemExit(f"Additive component missing before source restore: {relative}")
            target = addon_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        shutil.rmtree(REPO / "src/arash", ignore_errors=True)
        shutil.copytree(reference / "src/arash", REPO / "src/arash")
        shutil.rmtree(REPO / "tests", ignore_errors=True)
        shutil.copytree(reference / "tests", REPO / "tests")
        for relative in ("pyproject.toml", "scripts/release_gate.py"):
            destination = REPO / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(reference / relative, destination)

        for folder in ("sample_data", "config", "examples"):
            source = reference / folder
            destination = REPO / folder
            if source.exists():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(source, destination)
        if (reference / ".env.example").exists():
            shutil.copy2(reference / ".env.example", REPO / ".env.example")

        for relative in addon_paths:
            source = addon_root / relative
            destination = REPO / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        add_cli_integrations(REPO / "src/arash/cli.py")

        pyproject_path = REPO / "pyproject.toml"
        pyproject = pyproject_path.read_text(encoding="utf-8")
        if "marketstream =" not in pyproject:
            anchor = 'dev = ["pytest>=8.0", "ruff>=0.6"]\n'
            if anchor not in pyproject:
                raise SystemExit("Could not locate pyproject optional-dependencies anchor.")
            pyproject = pyproject.replace(
                anchor, anchor + 'marketstream = ["websockets>=13.0"]\n', 1
            )
        pyproject_path.write_text(pyproject, encoding="utf-8")

        gate_path = REPO / "scripts/release_gate.py"
        gate = gate_path.read_text(encoding="utf-8")
        if "tests/test_public_market_stream.py" not in gate:
            anchor = '"tests/test_mark_freshness.py", "tests/test_paper_currency_contract.py",'
            if anchor not in gate:
                raise SystemExit("Could not locate stream-test group in release gate.")
            gate = gate.replace(anchor, anchor[:-1] + ', "tests/test_public_market_stream.py",', 1)
        if "tests/test_research_diagnostics.py" not in gate:
            anchor = '"tests/test_release_gate.py",'
            if anchor not in gate:
                raise SystemExit("Could not locate diagnostics-test group in release gate.")
            gate = gate.replace(anchor, '"tests/test_release_gate.py", "tests/test_research_diagnostics.py",', 1)
        gate_path.write_text(gate, encoding="utf-8")

    for part in sorted(PARTS_DIR.glob(PART_GLOB)):
        part.unlink()

    manifest = REPO / "docs/SOURCE_SYNC_MANIFEST.md"
    if manifest.exists():
        manifest.write_text("""# Source Synchronization Manifest

## Identity

- Reference version: ARASH Foundation 28.0.0
- Reference archive SHA-256: 679f5a597857fe59a3e34ccd4b832058b7234d999171c74b660c46d7357bad3f
- Work branch: source-sync-28.0.0
- Pull request: https://github.com/pffoijeguff/ARASH-/pull/1
- Method: restore canonical source and tests from the checksum-verified archive; layer public-market-stream and statistical-diagnostic additions without replacing original components.

## Canonical source reconciliation

The canonical package, original test suite, configuration example, sample datasets, packaging metadata and release-gate script are restored directly from the archive after verifying its SHA-256. The new market-stream, CSCV/PBO and block-bootstrap functionality is integrated as additive code.

The restore workflow runs the full release gate before committing. The main branch is not modified by this workflow.

## Integration boundaries

- The public market stream consumes public order-book and public trade data only.
- PBO and bootstrap reports are diagnostics and do not generate trading actions.
- Software tests do not demonstrate a profitable trading edge.
- No live-order execution or successful live WebSocket session is claimed.
""", encoding="utf-8")

    audit = REPO / "docs/INTEGRATION_AUDIT.md"
    audit.write_text("""# Integration Audit — ARASH Foundation 28.0.0

The checksum-verified canonical package and complete reference test suite are restored on the development branch. Public market streaming, CSCV/PBO and moving-block-bootstrap components remain additive and are explicitly wired into the canonical CLI.

The restore workflow runs compilation, dependency checks, the package wheel/install acceptance check, Ruff, all grouped reference and additive regression tests, and the release-gate smoke scenarios. It writes machine-readable evidence to `artifacts/release-gate-branch.json` and commits the source only if the complete release gate succeeds.

A passing gate validates only the software behavior covered by those checks. It does not establish profitability, a live-order execution path, or provider compatibility beyond the tested public-data protocol. The main branch is only eligible for merge after the full gate and final PR-head checks pass.
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    complete, message, _ = archive_payload()
    print(message, flush=True)
    if args.check_only:
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as stream:
                stream.write(f"complete={'true' if complete else 'false'}\n")
        return 0
    restore()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
