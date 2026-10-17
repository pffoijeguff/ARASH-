# Integration Audit — ARASH Foundation 28.0.0

**Audit date:** 2026-10-17  
**Audited branch:** `source-sync-28.0.0`  
**Current audited commit:** `8c1720d539d6ac10d4b1c9db13c4e0a4e4f4d823`  
**Decision:** Do not merge until source parity is restored or every deviation is reviewed and accepted.

## Results at a glance

| Area | Result | Evidence |
|---|---|---|
| Current branch install / dependency consistency | PASS | GitHub Actions validation, Python 3.12 and 3.13 |
| Python source and test compilation | PASS | CI compile step |
| Focused lint | PASS | Ruff on the newly added research/stream components and test files |
| Checked-in regression suite | PASS | CI runs the branch's current two test modules (17 cases) |
| CLI smoke and synthetic diagnostics | PASS | `arash --help`, PBO demo, return-statistics demo, output boundary assertions |
| Integration with the full reference implementation | BLOCKED | Material source-tree differences remain |
| Full reference suite against this branch | NOT RUN / NOT PROVEN | The full reference suite is absent from the branch's checked-in tests |
| Live Nobitex WebSocket session | NOT VERIFIED | Parser and synthetic/unit-level checks are not a live exchange test |
| Main branch merge | BLOCKED | Source parity and complete branch-level regression evidence are required first |

## Source parity comparison

The synchronized branch has materially shorter versions of several core modules than the supplied 28.0.0 reference archive.

| Module | Reference archive | Development branch |
|---|---:|---:|
| `src/arash/cli.py` | 2,331 lines | 750 lines |
| `src/arash/paper/broker.py` | 1,248 lines | 635 lines |
| `src/arash/storage/sqlite_store.py` | 1,343 lines | 610 lines |
| `src/arash/paper/execution_batch.py` | 455 lines | 72 lines |
| `src/arash/research/selection_bias.py` | 454 lines | 52 lines |

These are not line-ending or formatting differences. The differences can remove commands and behavior from the reference implementation. The full source and original test suite must be restored from the reference archive, or a reviewed compatibility matrix must explain each intentional deviation. Do not interpret green focused CI as resolving this discrepancy.

## Component wiring reviewed

- `market-stream` wires the public book/trade stream to the rolling microstructure feature accumulator and emits structured JSON observations. It is a read-only path; no order-submission capability is added.
- `pbo-audit` accepts candidate-return series, delegates to the CSCV/PBO diagnostic, and emits a provenance hash with a no-trade-action boundary.
- `return-stats` delegates to circular moving-block bootstrap statistics and labels the report as a diagnostic, not a trading instruction.
- CI exercises CLI entry points and the synthetic PBO / return-statistics samples.
- Current branch tests exercise parsing, malformed payload handling, rolling-window bounds, and diagnostic validation. These tests do not validate all original ARASH command paths, storage/broker behavior, or live provider compatibility.

## Required merge gates

1. Restore the canonical 28.0.0 implementation and its full test suite; keep the new research/market-stream features as explicit additive changes.
2. Run the restored full tests, compilation, lint/security checks, package build/install, CLI smoke checks, and the release gate from a clean checkout. Publish actual run IDs and logs.
3. Review and fix every failure or document an intentional deviation with test coverage.
4. Recheck branch CI and compare the final PR head to `main`.
5. Merge only after parity and verification evidence are green.

## Financial and execution boundary

Passing software checks demonstrates only that the tested software behaved as expected in those conditions. It is not evidence of profitable trading. No live order execution or production readiness is claimed by this audit.
