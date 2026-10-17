# Source Sync Status — ARASH Foundation 28.0.0

## Current state

The branch \`source-sync-28.0.0\` contains the project's core offline source areas:
- CLI for CSV health/validation, public read-only market data, baseline backtesting, holdout evaluation, risk sizing, research grids, regime analysis, market intelligence, and execution sensitivity.
- A local SQLite store for candle imports, market-fetch lineage, paper-trade records, research-run records and artifact manifests.
- A persistent spot paper broker with idempotent client-order identifiers, explicit currency contracts, mandatory risk inputs for buys, paper fills, snapshots and a persistent kill switch.
- Research utilities for baseline backtests, candidate-family summaries, robustness scenarios, selection-bias diagnostics, manifests, and market-state change observations.

**This branch is not a verified release and is not claimed to be byte-for-byte or behavior-for-behavior identical to the supplied source archive.** Some modules were reconstructed or normalized while synchronizing the source through the GitHub interface. Full source-semantic parity remains outstanding.

## Verification policy

Automated tests and the full release gate were deliberately skipped for this source-transfer pass. No claim is made that this branch passes pytest, Ruff, installation checks, or a complete release gate.

The GitHub workflow is limited to package installation, compilation and CLI help invocation. These are small integration sanity steps, not proof of correctness or release readiness.

Archived evidence for the supplied ZIP is provenance only:
- Archive SHA-256: 4e0a677eb6a5438068609dc392f58c312066604ddde13641ed23fe627085d04b
- The archive recorded 301 passing tests, 11/11 smoke checks, 24 release-gate checks passed, zero failed and one incomplete because Ruff was unavailable.
- Those archived results are not results for this Git branch.

## Remaining source-sync tasks

1. Compare the behavior and file contents against the reference package and correct differences.
2. Reconcile the remaining implementation gaps in data snapshots, broker persistence, research workflows, and report schemas.
3. Keep public data integrations read-only and the paper-only boundary intact.
4. Decide and document the project license.
5. Only run tests and release verification in a later phase, not as a blocker for this source-transfer pass.
