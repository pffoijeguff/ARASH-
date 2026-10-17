# Source Synchronization Manifest

## Identity

- Reference version: ARASH Foundation 28.0.0
- Reference ZIP SHA-256: 4e0a677eb6a5438068609dc392f58c312066604ddde13641ed23fe627085d04b
- Public work branch: source-sync-28.0.0
- Pull request: https://github.com/pffoijeguff/ARASH-/pull/1
- Scope: source transfer, English public docs, local storage, research and paper-simulation integration.

## Main source areas

| Path | Responsibility |
| --- | --- |
| src/arash/cli.py | Command routing, argument validation and JSON reports. |
| src/arash/data/ | CSV loading, candle validation, market data health, session calendars, snapshots, and reconciliation. |
| src/arash/domain/ | Decimal-based OHLCV and closed-trade domain models. |
| src/arash/integrations/nobitex/ | Bounded, public read-only ticker/candle retrieval. |
| src/arash/paper/ | Durable local paper broker, simulated execution, batch simulation, and execution-cost sensitivity. |
| src/arash/risk/ | Long-only risk sizing, persisted-snapshot circuit breaker, and deterministic stress scenarios. |
| src/arash/research/ | Baseline backtests, holdout evaluations, market intelligence, regime labels, robustness, selection-bias notes, manifests, and report watch. |
| src/arash/reporting/ | Descriptive realized-trade reports. |
| src/arash/storage/ | SQLite candle store, market-snapshot lineage, local artifacts, and research-run records. |
| .github/workflows/ci.yml | Python 3.12/3.13 package install, compile, checked-in tests, CLI smoke check and synthetic diagnostic integration checks. |
| tests/ | Regression checks for research diagnostics, public feed payload parsing and rolling microstructure aggregation. |

## Parity audit and merge blocker

The uploaded ZIP remains the reference for exact historical source. A structural comparison shows that this Git branch is not yet behaviorally equivalent:

- Reference `src/arash/cli.py`: 2,331 lines; this branch: 750 lines.
- Reference `src/arash/paper/broker.py`: 1,248 lines; this branch: 635 lines.
- Reference `src/arash/storage/sqlite_store.py`: 1,343 lines; this branch: 610 lines.
- Several other research and execution modules are also substantially shorter in this branch.
- The command surface differs: the reference archive exposes additional workflow commands that are absent from this reconstructed branch.

This is a functional parity gap, not just a formatting difference. Do not merge this branch to `main` as the synchronized 28.0.0 source until the reference implementation and its tests are restored or every intentional deviation is audited and validated.

## Verification status

The current branch's GitHub Actions workflow passed on Python 3.12 and 3.13 at commit `7542e84c01da4758e425234da5ab2a0247150212`. The workflow checks package installation, Python compilation, the checked-in regression tests, CLI help, the synthetic PBO and return-statistics commands, and their non-execution output boundaries.

Those checks are useful but limited: the current branch contains 17 checked-in regression cases, not the full reference test suite. The reference archive has 301 unique test cases; archive-side passing results are not evidence that the reconstructed branch passes those tests. No live exchange WebSocket session, provider-side schema compatibility, production execution path or full release gate has been verified.

## Operating boundaries

- Public market-data requests are opt-in and read-only.
- Paper orders are local simulations using explicit caller-supplied reference prices.
- The broker does not submit live orders.
- Leverage, short selling, and FX conversion are disabled.
- Hashes provide integrity evidence for exact bytes; they do not establish provider authenticity, data truth, statistical validity, or strategy profitability.
