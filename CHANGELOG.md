# Changelog

## Unreleased — source synchronization work

The public source-sync-28.0.0 branch now includes a staged command-line interface for market-data sync/reconciliation, baseline backtests, chronological holdout evaluation, research robustness summaries, descriptive market intelligence, report provenance and offline execution sensitivity. A local SQLite store now records immutable market-data snapshots, source/data hashes and new/revised/unchanged observation counts. The paper broker persists simulated orders, fills, account snapshots and a manual risk kill switch.

This is repository synchronization work, not a new versioned release. Some code paths were reconstructed or normalized while transferring the source. No claim of byte-for-byte or behavior-for-behavior parity is made; the source transfer remains open.

Automated tests and the full release gate were deliberately skipped for this transfer phase. Live order submission remains out of scope.

## 28.0.0 — 2026-10-16

- Corrected per-instrument position-cap sizing so current exposure in the same instrument is deducted before sizing an additional BUY.
- Updated the paper broker to pass marked same-instrument exposure to the risk engine.
- Exposed --current-position-exposure in the advisory risk-check command.
- Added validation for inconsistent same-instrument and total-portfolio exposure values.
- Added regression coverage for incremental position-cap enforcement and invalid exposure inputs.
- Translated end-user research explanations in selected quantitative-review modules to English without changing their algorithms.

This is a risk-control and localization release, not evidence of trading profitability. Execution remains simulation-only.
