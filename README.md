# ARASH Foundation

**An offline-first quantitative research and paper-simulation framework.**

The public source-synchronization branch now contains a staged CLI, local SQLite storage, a persistent paper broker, selected market-data ingestion and quality tools, risk diagnostics, and offline candle-based execution simulation. The full 28.0.0 research suite has not yet been synchronized, so this is a working branch rather than a verified release.

> **Research-only boundary:** This project is intended for offline analysis and paper simulation. It does not support live order submission. It is not financial advice and does not establish a profitable trading strategy.

## Install and open the CLI

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install .
    python -m arash --help

Use the equivalent virtual-environment activation command on Windows PowerShell.

## Current staged command set

- **csv-health:** audit OHLCV CSV data for structural issues, timestamp problems, gaps and stale observations.
- **csv-validate:** strictly load local OHLCV data before downstream research.
- **market-fetch:** bounded, read-only public candle retrieval; does not access account credentials.
- **risk-check:** compute hypothetical long-only position sizing under explicit risk assumptions.
- **execution-simulate:** generate a bounded candle-based simulated execution report.
- **execution-stress:** compare explicit execution cost and capacity assumptions.

Examples:

    python -m arash csv-health sample_data/example_candles.csv
    python -m arash csv-validate sample_data/example_candles.csv
    python -m arash risk-check --equity 10000 --cash 10000 --entry-price 100 --stop-price 95

Paper-account methods are available in the source API and command handler module. The source branch is still being reconciled with the full reference package, so use the release status page to distinguish the staged subset from the complete archive functionality.

## Repository map

    src/arash/cli.py                       Staged command-line interface
    src/arash/data/                        CSV validation, health, snapshots and connectors
    src/arash/domain/                      Decimal-based domain models
    src/arash/integrations/nobitex/        Optional read-only public market-data client
    src/arash/paper/broker.py              Persistent offline spot-paper broker
    src/arash/paper/execution.py           Offline candle-based execution simulation
    src/arash/paper/execution_stress.py    Execution sensitivity scenarios
    src/arash/risk/                        Sizing, snapshot audit and stress analysis
    src/arash/storage/sqlite_store.py      Local market-data and research-record store
    src/arash/safety/                      Research/paper operating-mode guard
    docs/                                  Architecture, risk and research documentation
    sample_data/                           Demonstration inputs

## Safety and reproducibility

- Paper positions use caller-supplied reference prices; no market price is silently fetched for a paper order.
- BUY orders require an explicit risk policy and risk inputs; short selling and leverage are disabled.
- Public market-data access is read-only and bounded.
- Paper-account valuations use one currency; FX conversion is disabled.
- A report is conditional on its dataset, timestamps and assumptions. It does not guarantee real fills, capital preservation or profitability.
- Never commit credentials, private account data or unreviewed datasets.

## Synchronization and verification status

This branch is intentionally a partial source sync. The remaining research modules and full file parity with the cleaned 28.0.0 archive are outstanding. Unit tests were deliberately not run during this source-transfer pass. The GitHub workflow performs only package installation, compilation and CLI help verification; it does not claim a passing test suite.

See [Architecture](docs/ARCHITECTURE.md), [Research Protocol](docs/RESEARCH_PROTOCOL.md), [Risk and Safety](docs/RISK_AND_SAFETY.md), and [Release Status](docs/RELEASE_STATUS.md).

## License

An explicit license for reuse or redistribution has not yet been selected by the project owner.
