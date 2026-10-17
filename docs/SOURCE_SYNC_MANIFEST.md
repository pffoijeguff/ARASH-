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
| .github/workflows/ | Package/install, compile and CLI-help sanity workflow; no unit-test step. |

## Transfer caveats

Some modules in the public work branch were reconstructed or normalized based on the supplied archive instead of copied byte-for-byte. Behavioral equivalence has not been established. The ZIP archive remains the reference for exact historical source.

The test suite and release gate have been deliberately skipped during this source-transfer phase. The work branch is not a verified release and must not be merged to main as a finished release until the synchronization gaps are addressed.

## Operating boundaries

- Public market-data requests are opt-in and read-only.
- Paper orders are local simulations using explicit caller-supplied reference prices.
- The broker does not submit live orders.
- Leverage, short selling, and FX conversion are disabled.
- Hashes provide integrity evidence for exact bytes; they do not establish provider authenticity, data truth, statistical validity, or strategy profitability.
