# ARASH Development Status

## Product direction

ARASH is being developed as an ambitious research-driven quantitative platform centered on adaptive market analysis, rigorous validation, execution realism, portfolio-aware risk and end-to-end auditability. The goal is a coherent path from market data and hypothesis research to paper operation and, only after appropriate engineering and verification, controlled execution.

The current development branch contains market-data quality and public candle ingestion, a read-only public WebSocket order-book and trades feed, descriptive microstructure features, backtesting and evaluation workflows, robustness diagnostics, CSCV/PBO selection-instability analysis, circular block-bootstrap return uncertainty, risk sizing, local paper-account bookkeeping, execution scenarios and report provenance.

## Current implementation boundary

- Public market-data requests use public, read-only endpoints; the stream emits order-book/trade observations and does not submit exchange orders.
- Historical replay and paper execution are research/simulation features.
- Production exchange order routing, user-account channels, venue-side order/fill reconciliation and the complete real-time operating stack are not validated capabilities of this branch.
- Some components were reconstructed or normalized during synchronization. Their source and behavior are not yet equivalent to the 28.0.0 reference archive.

## Verification status

The latest focused branch CI run at code commit `24162f1e7bb3379f015f7a7b60501aac8ee61c3e` passed on Python 3.12 and 3.13. Each job installed the package and development extras, compiled source and tests, ran the checked-in regression tests, checked `python -m arash --help`, ran both synthetic research-diagnostic commands, and checked that their output makes no trading action.

The checked-in branch currently has 17 regression cases covering PBO/return-statistics validation and public stream parsing/rolling-feature integration. This is a focused verification layer, not the full release gate. A passing CI smoke job does not establish correctness of every module or live provider compatibility. Full lint/security/release-gate checks and live WebSocket verification have not been completed.

The supplied reference ZIP separately records:
- SHA-256: `4e0a677eb6a5438068609dc392f58c312066604ddde13641ed23fe627085d04b`
- 301 test cases, 11/11 smoke checks, and a release-gate summary of 24 checks passed, zero failed and one incomplete because Ruff was unavailable.

Those are reference-archive results, not results from the reconstructed Git branch.

## Source parity and merge gate

A structural check found important differences from the reference archive:

| Module | Reference archive | Development branch |
| --- | ---: | ---: |
| `src/arash/cli.py` | 2,331 lines | 750 lines |
| `src/arash/paper/broker.py` | 1,248 lines | 635 lines |
| `src/arash/storage/sqlite_store.py` | 1,343 lines | 610 lines |
| `src/arash/paper/execution_batch.py` | 455 lines | 72 lines |
| `src/arash/research/selection_bias.py` | 454 lines | 52 lines |

The command surface also differs, and the reference archive contains a much broader test suite. These are potential feature regressions, not cosmetic differences. Therefore the branch remains a draft and must **not** be merged to `main` as a synchronized 28.0.0 release until the reference source and tests are restored or every deviation is explicitly reviewed and validated.

## Immediate engineering priorities

1. Restore exact reference source for existing 28.0.0 functionality before layering new research modules onto it.
2. Run the reference test suite against that restored branch, then run lint, security and release-gate checks.
3. Add hermetic protocol/feature tests and validate provider interaction separately from CI mocks.
4. Preserve execution/risk boundaries and do not treat backtest diagnostics or software test results as evidence of strategy profitability.
5. Decide and document the project license.
