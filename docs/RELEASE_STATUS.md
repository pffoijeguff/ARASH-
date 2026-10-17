# Source Sync Status — ARASH Foundation 28.0.0

## Current state

This branch (source-sync-28.0.0) is a partial, public source-synchronization branch derived from the cleaned 28.0.0 reference package. It adds the staged CLI and selected data-quality, read-only market-data, risk-sizing, and offline execution modules.

**It is not yet a complete runnable mirror of the reference archive.** The full persistent paper broker, the complete SQLite market-data store, several research modules and the archived tests are not all present in this Git branch.

## Verification policy

Per the current source-transfer task, automated tests are not a blocker for this synchronization pass and have not been run against this branch. Therefore this page makes no claim that the branch passes the test suite, lint, installation, or hosted CI.

Archived evidence for the supplied 28.0.0 ZIP is documented separately below for provenance only:
- Archive SHA-256: 4e0a677eb6a5438068609dc392f58c312066604ddde13641ed23fe627085d04b
- The archive recorded 301 passing tests, 11/11 smoke checks, 24 release-gate checks passed, zero failed and one incomplete because Ruff was unavailable.
- Those archived results are not results for this Git branch.
- Fresh release verification and the complete source synchronization are still outstanding.

## Remaining source synchronization

1. Add the full SQLite market-data store and persistent paper broker.
2. Add the remaining research modules and original command coverage.
3. Compare the synchronized file set against the cleaned archive manifest.
4. Review packaging and CI only after code transfer is complete.
5. Keep live order submission out of scope.
