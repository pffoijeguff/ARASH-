# ADR-0001: Simulation-Only Modes in the Foundation Release

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

As a research system, ARASH must demonstrate data quality, computational correctness, reporting quality, and failure handling before introducing sensitive integrations.

## Decision

Foundation accepts only `research` and `paper` modes. The configuration parser rejects `live`, and there is no live order-submission path.

## Consequences

- The calculation and reporting core can be tested without exchange credentials.
- No real capital is involved in the supported execution path.
- External integrations require a separate review after acceptance criteria are met.
- Simulation results do not guarantee future returns or real-world execution quality.
