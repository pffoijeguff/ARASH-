# Architecture

ARASH Foundation is organized into functional layers so data, research, risk checks, simulated execution, and persistence remain independently testable.

```text
CLI / commands
     |
     v
Data ingestion and validation ---> Local market-data snapshots
     |                                      |
     v                                      v
Research / backtesting / evaluation / robustness audits
     |
     v
Risk assessment ---> Paper broker ---> Simulated execution reports
     |                                      |
     +--------------> SQLite ledger <-------+
                        |
                        v
                Reports and manifests
```

## Main modules

- `src/arash/cli.py`: command-line entry point and orchestration.
- `src/arash/data/`: parsing, data quality, sessions, reconciliation, health checks, and snapshots.
- `src/arash/research/`: backtesting, walk-forward evaluation, robustness checks, quantitative audits, and research reports.
- `src/arash/risk/`: explicit risk inputs, portfolio exposure checks, and stress diagnostics.
- `src/arash/paper/`: paper broker, simulated fills, and batch/stress execution models.
- `src/arash/storage/`: SQLite schema and local persistence.
- `src/arash/integrations/`: opt-in, read-only public market-data adapters.
- `scripts/release_gate.py`: reproducible local verification workflow.

## Design constraints

1. Research can run with local files and synthetic demo data.
2. External data access is opt-in and read-only.
3. The order path is simulated; live order submission is not supported.
4. Inputs, assumptions, and output limitations should be recorded and reviewable.
5. Database schema compatibility must be checked before writes or migration.
6. A content hash identifies bytes; it does not prove their origin or truth.
