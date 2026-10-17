# ARASH Roadmap — Toward an Elite Quantitative Trading Platform

This roadmap is ambitious by design. It focuses on the combination that distinguishes serious trading infrastructure: robust research, market-aware intelligence, realistic execution, portfolio-level risk and dependable operations.

## Workstream 1 — Source integrity and a dependable core

- [ ] Reconcile the current source branch against the reference archive and eliminate accidental behavioral divergence.
- [ ] Establish clean packaging, deterministic configuration, structured logging and consistent domain types.
- [ ] Define event contracts for market updates, signals, target positions, risk decisions, orders, acknowledgements, fills and accounting.
- [ ] Add regression coverage for accounting, order idempotency, data quality and critical risk invariants in the verification phase.
- [ ] Add dependency, secret-scanning and supply-chain checks before release.

## Workstream 2 — Market data as a first-class system

- [ ] Harden the initial public order-book stream with verified heartbeat/reconnect behavior, stale-feed alerts, sequence-gap detection and observable stream health.
- [ ] Expand streaming ingestion to multi-market trades, quotes, candles and instrument metadata, alongside venue-specific order-book events.
- [ ] Track exchange event time and local receive time; detect gaps, duplicates, clock skew and out-of-order updates.
- [ ] Build point-in-time storage with provenance, revisions and reproducible dataset snapshots.
- [ ] Expand cross-venue and cross-asset data support with explicit symbol, unit and precision contracts.

## Workstream 3 — Research quality beyond a single backtest

- [ ] Preserve chronological holdouts and add purged/embargoed validation for overlapping labels or holding periods.
- [ ] Add Combinatorial Purged Cross-Validation (CPCV) experiments where the dataset and research question support it.
- [ ] Verify and refine the new CSCV-based Probability of Backtest Overfitting (PBO) workflow; implement Deflated Sharpe Ratio (DSR) with documented assumptions and independent verification.
- [ ] Add nested model selection, ablation studies, benchmark-relative evaluation and stability checks across time and market regimes.
- [ ] Add bootstrapped uncertainty intervals, tail-risk summaries, turnover, exposure, capacity and drawdown-recovery metrics.
- [ ] Treat point-in-time feature availability and prevention of label/feature leakage as hard research gates.

## Workstream 4 — Market-aware strategy intelligence

- [ ] Establish a typed alpha/strategy interface and versioned strategy/model registry.
- [ ] Add regime-aware evaluation without assuming that a regime classifier predicts returns.
- [ ] Compare transparent baselines against nonlinear models and ensembles using identical leakage-controlled data splits.
- [ ] Evaluate feature stability, calibration, uncertainty and drift; retain a simple baseline when complexity does not add robust net value.
- [ ] Research cross-asset and cross-venue transfer only where data provenance and market mechanics justify it.

## Workstream 5 — Execution realism

- [ ] Replace candle-only execution approximations with pluggable, venue-specific models.
- [ ] Model maker/taker fees, bid-ask spread, slippage, latency, partial fills, rejects, funding/borrow costs where relevant, and market impact.
- [ ] Add order-book replay and queue-position sensitivity where trustworthy historical data is available.
- [ ] Stress cost and liquidity assumptions, including thin books, volatility spikes, gaps and degraded connectivity.
- [ ] Report gross and net results separately, including turnover, implementation shortfall and sensitivity to assumptions.
- [ ] Make execution batch scenarios share a defined liquidity budget when modelling a common venue, rather than treating independent fills as aggregate market capacity.

## Workstream 6 — Portfolio and risk control

- [ ] Evolve instrument-level sizing into portfolio-aware exposure and correlation constraints.
- [ ] Specify pre-trade limits for notional, concentration, leverage (only if intentionally supported), price collars and order rates.
- [ ] Add daily loss and drawdown policies with well-defined reset times and persistent kill-switch behavior.
- [ ] Include stale marks, missing balances, partial fills and reconciliation drift in risk scenarios.
- [ ] Require risk approval for all order-producing components; strategy code must not have direct bypasses.

## Workstream 7 — Online runtime and exchange integration

- [ ] Introduce an event-driven runtime with bounded queues, idempotent requests and explicit timeout/retry semantics.
- [ ] Implement exchange adapters behind one normalized interface and separate read-only data permissions from trading permissions.
- [ ] Add paper/shadow operation against live public data before considering any real order routing.
- [ ] Reconcile acknowledgements, fills, open orders, balances and positions after reconnect and restart.
- [ ] Add independent emergency stops, alerting, health endpoints, audit logs and operational recovery procedures.
- [ ] Gate any live deployment behind separate authorization, staged rollout, limits and a verified release process.

## Workstream 8 — Observability and release engineering

- [ ] Emit structured, correlated logs and per-run manifests.
- [ ] Measure decision latency, ingestion lag, stale data, rejection reasons, realized costs and forecast drift.
- [ ] Track data/model/config versions and make rollback procedures explicit.
- [ ] Establish reproducible CI, security checks, supported Python versions and release artifacts.

## Definition of a credible milestone

A milestone is complete only when the capability exists in code, has clear contracts and documentation, and has appropriate verification evidence. A roadmap item or architectural diagram is a target—not proof of implementation. Attractive backtest metrics alone are not sufficient evidence of a durable trading edge.

## Current development status

The current synchronization branch is under development and may contain defects or incomplete integrations. The present phase prioritizes architecture and source reconciliation; tests and the full release gate were skipped by request and are not represented as passing.
