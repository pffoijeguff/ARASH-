# ARASH Foundation

**An offline-first quantitative research and paper-simulation framework.**

ARASH Foundation brings together local OHLCV quality checks, read-only public market-data retrieval, reproducible baseline backtests, risk sizing, paper-account bookkeeping, and candle-based execution research. The public branch \`source-sync-28.0.0\` is an active source-synchronization work branch—not a verified release.

> **Research-only boundary:** ARASH is designed for offline analysis and paper simulation. It does not support live order submission. It is not financial advice and does not establish a profitable trading strategy.

## Install and launch

Requires Python 3.12 or newer.

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install .
    python -m arash --help

On Windows PowerShell, activate the environment with \`.venv\\Scripts\\Activate.ps1\`.

## Command groups

| Command | Purpose |
| --- | --- |
| \`csv-health\` | Audit a CSV before research; report structural problems, gaps, and stale observations. |
| \`csv-validate\` | Strictly load a single homogeneous OHLCV series. |
| \`market-fetch\` | Fetch bounded public OHLCV data through a read-only provider. |
| \`backtest\` | Run the buy-and-hold or SMA-crossover research baseline. |
| \`evaluate\` | Run a fixed-parameter chronological holdout comparison. |
| \`quant-audit\` | Report accounting reconciliation and descriptive trade metrics. |
| \`robustness\` | Compare declared fee, slippage, sizing, and chronological subperiod scenarios. |
| \`research-grid\` | Produce a bounded candidate grid without automatically selecting a winner. |
| \`selection-bias-audit\` | Summarize the size and outcome spread of a declared candidate family. |
| \`regime-analysis\` | Describe prior-only market regimes from candle data. |
| \`market-intelligence\` | Generate descriptive trend, momentum, volatility, volume, and data-quality fields. |
| \`market-watch\` | Compare two saved market reports and emit change diagnostics, not trade signals. |
| \`research-pipeline\` | Run the CSV health gate before a baseline simulation. |
| \`risk-check\` | Calculate a hypothetical long-only position size using explicit risk inputs. |
| \`execution-simulate\` | Produce an offline candle-based execution trace. |
| \`execution-stress\` | Compare declared execution-cost and participation scenarios. |
| \`paper-account-create\` and related \`paper-*\` | Maintain a local simulated account, orders, snapshots, and risk-control records. |

Examples:

    python -m arash csv-health sample_data/example_candles.csv
    python -m arash csv-validate sample_data/example_candles.csv
    python -m arash backtest sample_data/research_demo_320.csv --strategy buy-hold
    python -m arash market-intelligence sample_data/research_demo_320.csv

See the [CLI reference](docs/CLI_REFERENCE.md) for more examples and the [paper-account runbook](docs/PAPER_ACCOUNT_RUNBOOK.md) for local simulation commands.

## Safety and research integrity

- Public data connectors are read-only; account credentials are not required for market fetching.
- Paper-account orders use a caller-supplied reference price and never reach an exchange.
- BUY orders require explicit risk inputs; short selling and leverage are disabled.
- Currency conversion is disabled in the local paper ledger. Instrument quote currency must match the account currency.
- Candle-based execution uses modeled fills, not order-book depth or actual venue fills.
- Research outputs identify assumptions and data limitations. Historical or synthetic results do not guarantee future outcomes.
- Never commit credentials, private account data, local ledgers, or datasets that you do not have permission to publish.

## Synchronization status

This branch contains the core modules for data validation, local storage, paper-account bookkeeping, risk analysis, baseline backtests, research reports, and execution simulation. Some components were reconstructed or normalized during synchronization and have **not been proven byte-for-byte or behavior-for-behavior identical** to the supplied 28.0.0 reference archive. Full semantic parity remains outstanding.

The current GitHub workflow only attempts package installation, compilation, and CLI help invocation. The test suite and release gate were deliberately not used as blockers during source transfer and have not been run against this branch. Do not treat this work branch as a verified release.

See [Architecture](docs/ARCHITECTURE.md), [Research Protocol](docs/RESEARCH_PROTOCOL.md), [Risk and Safety](docs/RISK_AND_SAFETY.md), and [Release Status](docs/RELEASE_STATUS.md).

## License

An explicit license for external reuse or redistribution has not yet been selected by the project owner.
