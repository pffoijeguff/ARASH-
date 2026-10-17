# ARASH Risk and Operational Controls

ARASH is being designed with a risk-first control plane. Signal quality cannot compensate for uncontrolled order flow, stale data, incorrect accounting or unrealistic execution assumptions.

## Current branch boundary

The current source branch provides risk diagnostics, position sizing and a simulated paper-account workflow. Public market-data access is read-only. A simulated fill is not evidence of an exchange fill, and the current branch should not be assumed to submit live orders.

## Target pre-trade controls

- Instrument permission and order-type validation.
- Maximum order notional, position size, gross/net exposure and concentration checks.
- Price collars, quantity/precision validation and order-rate throttles.
- Explicit fee, spread, slippage and minimum-notional assumptions.
- Stale-market-data and excessive-feed-lag rejection.
- Daily loss, drawdown and instrument-level circuit breakers.
- Persistent global and per-strategy kill switches that fail closed.
- Idempotent client order identifiers and prevention of duplicate submission.
- Clear reject reasons, durable audit records and post-restart reconciliation.

## Operational failure modes to design for

- Exchange disconnects, API timeouts, rate limits and partial responses.
- Out-of-order, duplicated, stale or missing market events.
- Partial fills, rejected orders and ambiguous submission acknowledgements.
- Differences between internal and venue balances, positions or open orders.
- Unexpected fees, market impact, funding/borrow costs and liquidity gaps.
- A strategy, data feed or model becoming unstable after a regime change.

When internal and external state disagree, the system should stop increasing risk until it has reconciled the discrepancy. Restart behavior, retry policy and stop-state persistence must be explicit.

## Research and execution interpretation

Historical simulation, paper trading and stress tests establish behavior only under their declared data and assumptions. They cannot guarantee capital preservation or future returns. Risk outputs are only as sound as their marks, exposures, currency units, timing, fees and policy inputs.

## Development status

Controls and adapters are being developed iteratively. The current branch may contain defects or incomplete integrations; it is not a verified production release.
