# ARASH Foundation

**An offline-first quantitative research and paper-simulation framework.**

The public source-synchronization branch contains a staged CLI, local SQLite storage, a persistent paper broker, market-data quality tools, risk diagnostics, research summaries, and candle-based execution simulation. It remains an active synchronization work branch, not a verified release.

> **Research-only boundary:** ARASH is designed for offline analysis and paper simulation. It does not support live order submission. It is not financial advice and does not establish a profitable trading strategy.

## Install and launch

Requires Python 3.12 or newer.

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install .
    python -m arash --help

On Windows PowerShell, activate with \`.venv\\Scripts\\Activate.ps1\`.

## Command groups

| Command | Purpose |
| --- | --- |
| \`csv-health\`, \`csv-validate\` | Audit and validate local OHLCV data. |
| \`market-fetch\` | Bounded, read-only public candle retrieval. |
| \`backtest\`, \`evaluate\` | Run a baseline simulation and fixed-configuration chronological holdout. |
| \`quant-audit\`, \`robustness\`, \`research-grid\`, \`selection-bias-audit\` | Review bookkeeping, sensitivity and candidate-family selection bias. |
| \`regime-analysis\`, \`market-intelligence\`, \`market-watch\` | Descriptive regime, indicator and report-change diagnostics. |
| \`research-pipeline\`, \`research-manifest\` | Gate research on data-quality findings and record report provenance. |
| \`risk-check\` | Calculate hypothetical long-only sizing under explicit assumptions. |
| \`execution-simulate\`, \`execution-stress\`, \`execution-batch\` | Produce offline modeled execution reports. |
| \`paper-*\` | Maintain a local simulated account, paper orders, snapshots and risk controls. |

Examples:

    python -m arash csv-validate sample_data/research_demo_320.csv
    python -m arash backtest sample_data/research_demo_320.csv --strategy buy-hold
    python -m arash market-intelligence sample_data/research_demo_320.csv

See the [CLI reference](docs/CLI_REFERENCE.md) and [paper-account runbook](docs/PAPER_ACCOUNT_RUNBOOK.md).

## Safety and research integrity

- Public data connectors are read-only; account credentials are not required for market fetching.
- Paper-account orders use caller-supplied reference prices and never reach an exchange.
- BUY orders require explicit risk inputs; short selling and leverage are disabled.
- Paper-account valuation uses one currency; FX conversion is disabled.
- Candle-based execution uses modeled fills, not order-book depth or actual venue fills.
- A backtest, stress scenario, or hash-bearing report does not guarantee correctness or future performance.
- Never commit credentials, private account data, local ledgers, or datasets that you do not have permission to publish.

## Synchronization and verification status

This branch contains the major core source areas, including market-data validation, local storage, paper-account bookkeeping, risk analysis, baseline backtests, research summaries, and execution simulation. Some components were reconstructed or normalized during synchronization and have not been proven byte-for-byte or behavior-for-behavior identical to the supplied 28.0.0 reference archive. Full semantic parity remains outstanding.

The GitHub workflow performs package installation, compilation and CLI help invocation only. The test suite and full release gate have been deliberately skipped during the current source-transfer phase. Do not treat this work branch as a verified release.

See [Architecture](docs/ARCHITECTURE.md), [Research Protocol](docs/RESEARCH_PROTOCOL.md), [Risk and Safety](docs/RISK_AND_SAFETY.md), and [Release Status](docs/RELEASE_STATUS.md).

## License

An explicit license for external reuse or redistribution has not yet been selected.
