# ARASH Foundation — Roadmap

Items below are plans until implemented, tested, and documented with evidence.

## Priority 0 — Publish a verifiable source baseline

- [ ] Synchronize the reviewed ARASH Foundation 28.0.0 source tree, tests, packaging metadata, scripts, configuration examples, and sample data into this repository.
- [ ] Exclude generated build outputs, `*.egg-info`, local databases, logs, private data, caches, and credentials.
- [ ] Confirm that public-facing documentation is English and accurately describes version 28.0.0.
- [ ] Run compilation, all tests, smoke checks, packaging checks, and the complete release gate from a clean checkout.
- [ ] Install Ruff and record its actual result.
- [ ] Verify the intended Python version matrix and hosted CI.
- [ ] Publish installation instructions only after they work from a clean clone.

## Priority 1 — Reproducible research

- [ ] Make dataset, configuration, fold boundaries, candidate-family definitions, and transaction-cost assumptions inspectable in reports.
- [ ] Expand deterministic tests for temporal splits, look-ahead checks, gaps, and data-provenance mismatches.
- [ ] Keep synthetic examples small, deterministic, clearly labeled, and independent of network access.
- [ ] Version report schemas so older evidence cannot be silently interpreted under newer semantics.

## Priority 2 — Risk and simulation fidelity

- [ ] Continue regression coverage for position sizing, exposure limits, stale marks, daily loss, drawdown, and kill-switch behavior.
- [ ] Test order-state transitions, partial fills, capacity constraints, fees, spread, and slippage with explicit fixtures.
- [ ] Make simulation assumptions visible in machine-readable reports.
- [ ] Test database migrations on fresh and representative prior-version ledgers.

## Priority 3 — Release engineering

- [ ] Establish a clean-checkout release procedure with reproducible artifact manifests.
- [ ] Verify wheel contents, metadata, CLI entry points, and isolated installation in automation.
- [ ] Add dependency and supply-chain review appropriate to the package.
- [ ] Keep incomplete checks visible rather than bypassing them.

## Out of scope for the current research-only baseline

- Live exchange order submission.
- Real-money account connectivity or credential handling.
- Claims that a strategy is profitable or guaranteed to outperform a benchmark.

Any future live-execution proposal requires separate design, security review, operational validation, and explicit approval.
