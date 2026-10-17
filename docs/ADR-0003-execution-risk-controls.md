# ADR-0003: Candle Execution Research and Persisted Paper Risk Halt

- **Status:** Accepted for Foundation 4.0.0
- **Date:** 2026-10-13

## Context

ARASH already supported offline backtests and an immediate full-fill paper broker. That is useful for accounting tests, but it cannot express volume-constrained fills, partial fills, limit-touch scenarios, or a durable account-level halt after portfolio-risk violations.

## Decision

1. Add a pure, deterministic `simulate_execution` function over local OHLCV bars.
2. Require timezone-aware `submitted_at` and only examine bars with `timestamp > submitted_at`.
3. Cap each candle's fill at a configured fraction of its reported volume. Charge explicit fee, base slippage, half-spread and square-root participation impact for market fills. Limit fills are conservatively priced at the limit after an OHLC touch.
4. Fingerprint the eligible candle OHLCV series and complete simulation configuration for audit/replay.
5. Add a SQLite-backed account kill switch. Portfolio audit derives daily and drawdown baselines from persisted paper equity observations and trips the switch after a detected breach.
6. While a switch is active, every new paper order is rejected inside the broker transaction. Clearing it requires a reason plus explicit confirmation and is recorded in the audit events.

## Consequences

- Partial-fill outcomes and cost sensitivity can now be explored without external network dependencies.
- Risk controls survive process restarts and are independent of callers remembering to supply a flag once the account is halted.
- OHLCV is not order-book data. The execution simulator is not venue-accurate and does not update account cash/positions; it reports a modeled execution trace only.
- Risk audit cannot detect an intraday peak or loss that was never captured by a persisted snapshot. It uses operator-provided marks and UTC-day baselines.
- Immediate paper orders remain for compatibility. Per-trade position sizing is still opt-in (`--risk-enabled`) until future releases make account-state-derived sizing the default.
- No live execution adapter is introduced. A future live adapter would require a separate safety review and reconciliation design.
