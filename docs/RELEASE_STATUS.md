# ARASH Development Status

## Product direction

ARASH is being developed as a research-driven quantitative trading platform centered on adaptive market analysis, rigorous validation, execution realism, portfolio-aware risk and end-to-end auditability. The goal is a coherent path from market data and hypothesis research to paper operation and, only after appropriate engineering and verification, controlled production execution.

The current branch contains market-data quality and public candle ingestion, an initial public WebSocket order-book stream with REST bootstrap, top-of-book/microprice/spread/depth observations, backtesting and evaluation, robustness diagnostics, risk sizing, paper-account bookkeeping, execution scenarios and report provenance.

## Current implementation boundary

- Public market-data adapters are read-only; the initial live WebSocket path publishes descriptive order-book snapshots only.
- Historical replay and paper execution are supported as research/simulation modes.
- Production exchange order routing, user-account channels, venue-side order/fill reconciliation and the complete real-time operating stack remain development milestones.
- Some components were reconstructed or normalized during synchronization and have not been proven byte-for-byte or behavior-for-behavior identical to the reference archive.

## Verification status

The source branch is under development and may contain defects or incomplete integrations. Automated tests and the full release gate were deliberately skipped for this source-transfer phase. No claim is made that this branch passes tests, lint, installation checks or a full release gate.

The supplied reference ZIP recorded the following archive metadata, for provenance only:
- SHA-256: 4e0a677eb6a5438068609dc392f58c312066604ddde13641ed23fe627085d04b
- 301 passing tests, 11/11 smoke checks, 24 gate checks passed, zero failed and one incomplete because Ruff was unavailable.

Those are archive-reported results and are **not** verification results for this Git branch.

## Immediate engineering priorities

1. Reconcile source behavior against the reference package and resolve structural inconsistencies.
2. Strengthen research validation, data lineage and selection-bias controls.
3. Move execution modeling toward venue-specific costs, liquidity and fill behavior.
4. Build toward an event-driven online runtime with risk-gated execution and reliable reconciliation.
5. Establish CI, security and release verification in the dedicated verification phase.
6. Decide and document the project license.
