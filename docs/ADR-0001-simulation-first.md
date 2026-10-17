# ADR-0001: Staged Execution and Risk-Gated Promotion

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

ARASH is intended to evolve toward an online-capable research-to-execution platform. That ambition requires more than generating strategy signals: source integrity, market-data quality, order semantics, risk enforcement, accounting, venue reconciliation and operational recovery must fit together. Introducing unrestricted real-money execution before those contracts are dependable would couple research defects directly to external side effects.

## Decision

The foundation release supports research and paper modes. The configuration parser rejects live mode, and this branch has no production order-submission path. Online read-only market-data retrieval is allowed as an explicit capability; deterministic replay remains a research mode rather than the product's identity.

Any later order-routing adapter must be introduced as a separate reviewed milestone behind explicit risk approval, bounded permissions, idempotency, reconciliation, monitoring, kill switches and a verified release process.

## Consequences

- Research and paper workflows can be developed without exchange trading credentials.
- Online market data can be studied while order execution remains simulated.
- A future production adapter must pass a separate technical and operational review.
- Simulation and historical results do not guarantee future returns or real-world execution quality.
