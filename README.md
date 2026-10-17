# ARASH Foundation

**An offline-first quantitative research and paper-trading framework.**

ARASH Foundation provides a reproducible environment for historical market-data research, backtesting, risk diagnostics, simulated execution, portfolio analysis, and auditable local research records. The project is designed to make assumptions and limitations explicit rather than treating a backtest as evidence of future performance.

> **Research-only boundary:** ARASH Foundation 28.0.0 is intended for offline research and paper simulation. It does not support live order submission. It is not financial advice and does not establish a profitable trading strategy.

## Project scope

- **Market-data validation:** CSV parsing, data-quality checks, session-aware validation, reconciliation, and content-addressed snapshots.
- **Quantitative research:** Backtests, walk-forward evaluation, cost sensitivity, prefix-invariance checks, strategy comparisons, and selection-bias diagnostics.
- **Risk controls:** Explicit risk inputs, portfolio-exposure checks, drawdown diagnostics, stress testing, and paper-broker safeguards.
- **Simulated execution:** Paper-order workflows and modeled execution constraints; fills are simulated, not exchange-confirmed.
- **Auditability:** Local SQLite records, reproducible manifests, release-gate checks, and test evidence.
- **Optional read-only data access:** Public market-data connectors are opt-in. Research can also run against local sample data without network access.

## Quick start

**Requirements:** Python 3.12 or newer.

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m arash --help
```

Run the automated tests:

```bash
python -m pytest -q
```

Run the local release gate (writes a generated JSON report):

```bash
python scripts/release_gate.py --output artifacts/release-gate-local.json
```

Generated databases, credentials, local environment files, build outputs, and release-gate results are excluded from version control by default. A placeholder `.env.example` is included; it contains no credentials.

## Repository map

```text
src/arash/                 Application package
  data/                    Loaders, quality checks, snapshots, and sync helpers
  research/                Backtesting, evaluation, robustness, and quant audits
  risk/                    Risk assessment and stress diagnostics
  paper/                   Simulated broker and execution models
  storage/                 Local SQLite schema and persistence
  integrations/            Optional read-only public market-data adapters
tests/                     Automated test suite
scripts/release_gate.py    Reproducible local release checks
sample_data/               Synthetic demonstration data
config/                    Example-only configuration
docs/                      Architecture, research protocol, and safety notes
artifacts/                 Sanitized release-gate evidence for 28.0.0
```

## Quality evidence and limitations

The included release-gate artifact records an archived run from **2026-10-16** using CPython 3.13.5: 24 checks passed, 0 failed, and 1 remained incomplete because Ruff was unavailable in that environment. The archive records 301 passing tests and 11/11 smoke checks. These are **archived results**, not a claim that the suite was rerun against every current development environment. Python 3.12 and hosted GitHub Actions must be verified by CI before the release can be considered fully verified. See [release status](docs/RELEASE_STATUS.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Research protocol](docs/RESEARCH_PROTOCOL.md)
- [Risk and safety boundaries](docs/RISK_AND_SAFETY.md)
- [Release status](docs/RELEASE_STATUS.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## License

No explicit open-source license has been supplied with this archive. The repository owner should choose and add a license before granting permission for external reuse or redistribution.
