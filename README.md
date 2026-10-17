# ARASH Foundation

**An offline-first quantitative research and paper-simulation framework.**

ARASH Foundation is being synchronized into this repository from the 28.0.0 reference archive. This branch contains the public documentation and a staged source foundation. It is a work branch, not a verified release.

> **Research-only boundary:** This project is intended for offline analysis and paper simulation. It does not support live order submission. It is not financial advice and does not establish a profitable trading strategy.

## Commands in the staged source branch

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[dev]"
    python -m arash --help

The currently staged CLI focuses on:
- **csv-health:** audit local OHLCV CSV data and identify structural issues, timestamp problems, gaps and stale observations.
- **csv-validate:** load strict OHLCV CSV rows before downstream research.
- **market-fetch:** optional, bounded, read-only public candle retrieval.
- **risk-check:** calculate hypothetical long-only sizing under explicit stop, exposure and loss assumptions.
- **execution-simulate:** generate an offline candle-based simulated execution report.
- **execution-stress:** compare explicit modeled execution-cost and participation scenarios.

Examples:

    python -m arash csv-health sample_data/example_candles.csv
    python -m arash csv-validate sample_data/example_candles.csv

These commands do not submit trades. Market fetch is read-only; analysis and execution reports are conditional on their declared input data and assumptions.

## Current branch state

This branch is a source-synchronization work in progress. The archive's full persistent broker, SQLite market-data store, and complete research command suite are not yet all present in this Git branch, so this branch must not be treated as a complete replacement for the downloaded source package. No test suite or release gate is being used as a blocker for source transfer; fresh verification remains a later release step.

## Repository map

    src/arash/cli.py                       Staged command-line interface
    src/arash/data/                        CSV validation, health, snapshots and connectors
    src/arash/domain/                      Decimal-based domain models
    src/arash/integrations/nobitex/        Optional read-only public market-data client
    src/arash/paper/execution.py           Offline candle-based execution simulation
    src/arash/paper/execution_stress.py    Execution sensitivity scenarios
    src/arash/risk/                        Sizing, persisted-snapshot audit and stress analysis
    src/arash/safety/                      Research/paper operating-mode guard
    docs/                                  Architecture, risk and research documentation
    sample_data/                           Synthetic or demonstration inputs

## Risk and reproducibility

- Keep dataset identity, timestamp semantics, assumptions, fees and simulated costs explicit.
- Do not treat backtests, stress scenarios or risk estimates as guarantees.
- Data hashes establish byte-level identity, not source authenticity.
- Paper fills and simulated stops are not real execution outcomes.
- Do not commit API credentials, private account data, local ledgers or unreviewed datasets.

See Architecture, Research Protocol, Risk and Safety, and Release Status in the docs folder.

## License

The project owner has not yet supplied an explicit license for external reuse or redistribution.
