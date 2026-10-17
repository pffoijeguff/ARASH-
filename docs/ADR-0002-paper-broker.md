# ADR-0002: Persistent, Idempotent Paper Broker

- **Status:** Accepted
- **Date:** 2026-10-12
- **Originating version:** 0.5.0

## Context

Simulation development needs persistent account state across restarts. Retrying an order request must not cause the same order to be applied twice.

## Decision

Implement a `PaperBroker` separate from the backtest candle loop. It runs offline, accepts a reference price from its caller, and stores a unique per-account `client_order_id` with a fingerprint of request parameters. Orders, fills, cash/position changes, and account events are recorded in one SQLite transaction.

Only spot-like purchases funded by available cash and sales up to the open long position are allowed. Leverage and short selling are disabled. Risk rejections are recorded without changing balances.

## Consequences

- Restarts and retries become more auditable and safer.
- Financial values are calculated with `Decimal`.
- Reference marks are caller-supplied; the broker is not a market-data connector.
- Assumptions of full fills and simplified slippage remain important limitations.
- This decision does not create permission or a path for live order submission.
