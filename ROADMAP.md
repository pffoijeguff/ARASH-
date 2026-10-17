# ARASH Foundation — Roadmap

This roadmap separates source-publication work from research-engine improvements. Items are plans until implemented, tested, and documented with evidence.

## Priority 0 — Publish a verifiable source baseline

- [ ] Obtain and verify the authoritative ARASH Foundation 30.0.0 archive against its SHA-256 checksum.
- [ ] Review source, test fixtures, examples, reports, and packaging files for secrets, private data, local paths, databases, caches, and accidental artifacts.
- [ ] Synchronize the intended source tree, tests, examples, packaging metadata, and release scripts into this repository.
- [ ] Confirm that the published tree matches the reviewed source snapshot and that no undocumented modifications were introduced.
- [ ] Re-run compilation, all test groups, smoke checks, wheel checks, and the complete release gate from a clean checkout.
- [ ] Install Ruff and resolve its outstanding check.
- [ ] Add hosted CI and verify the intended Python compatibility matrix, including Python 3.12, which was not confirmed by the 30.0.0 report.
- [ ] Add verified installation and development instructions only after these steps pass.

## Priority 1 — Reproducible research

- [ ] Document canonical dataset fingerprints and how they differ from raw-file byte hashes.
- [ ] Make dataset, configuration, fold boundaries, candidate-family definitions, random seeds, and cost assumptions easy to inspect in every applicable report.
- [ ] Expand deterministic tests for temporal splits, look-ahead checks, data gaps, and data-provenance mismatches.
- [ ] Keep synthetic examples small, deterministic, clearly labeled, and independent of network access.
- [ ] Validate report schemas and versioning so older evidence can be interpreted without silently assuming newer semantics.

## Priority 2 — Risk and simulation fidelity

- [ ] Continue regression coverage for position sizing, exposure limits, stale marks, daily loss, drawdown, and kill-switch behavior.
- [ ] Test order-state transitions, partial fills, capacity constraints, fees, spread, slippage, and market-impact assumptions with explicit fixtures.
- [ ] Make every simulated execution assumption visible in machine-readable reports.
- [ ] Test database migrations on both fresh and representative prior-version ledgers.

## Priority 3 — Release engineering and maintainability

- [ ] Establish a clean-checkout release procedure with reproducible artifact manifests.
- [ ] Verify wheel contents, metadata, CLI entry points, and isolated installation in automation.
- [ ] Add dependency and supply-chain review appropriate to the actual package configuration.
- [ ] Keep release claims linked to machine-readable evidence and preserve incomplete gate states.
- [ ] Add a change log and migration notes for every published version.

## Out of scope for the current research-only release

- Live exchange order submission.
- Real-money account connectivity or credential handling.
- Claims that a strategy is profitable, production-safe, or guaranteed to outperform a benchmark.

Any future live-execution proposal requires a separate design, threat model, operational review, and explicit approval. It must not be smuggled into the research roadmap as a routine feature.