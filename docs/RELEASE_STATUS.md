# Source Sync Status — ARASH Foundation 28.0.0

## Current state

The branch source-sync-28.0.0 now contains:
- Staged CLI for CSV health, strict CSV validation, public read-only candle retrieval, hypothetical risk sizing, execution simulation and execution sensitivity reports.
- A SQLite-backed spot paper broker with idempotent client-order IDs, currency-contract checks, explicit buy risk gates, local order/fill records and a persistent kill switch.
- A SQLite store for local market candles, sync metadata, artifacts and research-run records.
- CSV/data-quality utilities, point-in-time snapshot primitives, risk sizing and stress diagnostics, and English-language documentation.

This is still a **partial source synchronization**, not a complete mirror of the supplied archive. The full historical research suite, several original data-store capabilities, and parity across every source module remain outstanding.

## Verification policy

Automated tests were deliberately skipped for this source-transfer pass, as requested. No claim is made that this branch passes the test suite, Ruff, or a complete release gate.

The branch's GitHub workflow is limited to package installation, Python compilation, and CLI help invocation. These are basic sanity checks, not a substitute for test coverage or a release review.

Archived evidence for the supplied ZIP is retained only as provenance:
- Archive SHA-256: 4e0a677eb6a5438068609dc392f58c312066604ddde13641ed23fe627085d04b
- The archive recorded 301 passing tests, 11/11 smoke checks, 24 release-gate checks passed, zero failed and one incomplete because Ruff was unavailable.
- Those archived results are not results for this Git branch.

## Remaining synchronization work

1. Add the remaining research modules and original command coverage.
2. Compare the branch's tracked file set against the cleaned source archive.
3. Preserve the paper-only boundary and ensure public data integrations remain read-only.
4. Decide and document the license.
5. Run tests and release verification only when the source sync is sufficiently complete and the user requests that phase.
