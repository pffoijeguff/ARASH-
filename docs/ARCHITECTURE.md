# ARASH System Architecture

## Design intent

ARASH is being engineered as a research-driven, online-capable quantitative trading platform—not as an offline-only tool. Local datasets and deterministic replay are important laboratory modes: they let the same questions be studied repeatedly, with controlled inputs. They do not replace the intended real-time data, portfolio, execution and operational layers.

The core principle is separation of concerns with traceable contracts. A strategy proposes an intent; the portfolio layer converts intents into target exposure; an independent risk layer approves, constrains or rejects them; execution turns approved intents into orders; accounting records confirmed state; observability makes every transition inspectable.

## Target architecture

    Exchange and market data sources
      - Public REST snapshots
      - WebSocket trades, quotes and order-book updates
      - Reference, funding and instrument metadata
                    |
                    v
        Ingestion, normalization, quality gates
                    |
                    v
        Event bus and point-in-time market state
                    |
           +--------+------------------+
           |                           |
           v                           v
      Feature/regime services    Data quality and drift
           |                           |
           v                           |
      Strategy/alpha/model registry    |
           |                           |
           v                           |
      Portfolio construction <---------+
           |
           v
      Independent pre-trade risk gate
           |
           v
      Execution planner and venue adapter
           |
           v
      Order, acknowledgement, fill and reconciliation events
           |
           v
      Portfolio accounting and durable ledger
           |
           v
      Metrics, alerts, run manifests and audit trail

A resilient runtime should also include bounded queues, idempotent command identifiers, timeouts, retry policies, stale-feed detection, sequence-gap handling, circuit breakers, rate-limit awareness, a global and per-strategy kill switch, and controlled recovery after restart. These controls are part of the design, not optional embellishments.

## Architecture rules

1. **Research/live semantic parity:** market replay, paper operation and any future live adapter should share domain contracts and decision logic wherever practical. Differences in latency and available data must be explicit, never silently ignored.
2. **Data is a versioned input:** preserve source, venue, instrument, interval, event/receive timestamps, normalization rules, revisions and integrity digests. Prevent look-ahead, survivorship and stale-data contamination.
3. **A strategy cannot bypass risk:** strategy code emits an intent; a separate control path owns exposure, order-size, price collars, rate limits, trading permissions and stop conditions.
4. **Execution is a model and a system:** distinguish decision price, arrival price, limit/market behavior, fees, spread, slippage, queue position, partial fills, rejects, latency, market impact and venue-specific rules. Candle-based fills must never be described as exchange fills.
5. **Accounting is authoritative:** derive positions, cash, fees, realized/unrealized P&L and exposure from normalized order/fill/ledger events; reconcile internal state against venue state before any real deployment.
6. **Models are governed components:** version features, parameters, training data windows, model artifacts, benchmarks and promotion decisions. Monitor drift and use explicit rollback rules.
7. **Evidence travels with results:** each research run should record code version, configuration, data fingerprint, instrument universe, time range, assumptions, benchmark, candidate count and outputs.
8. **Fail safely:** stale data, invalid state, breached limits or a disconnected venue should reduce capability or halt order flow—not automatically trigger more trading.

## Current branch mapping

- src/arash/cli.py: CLI and command orchestration.
- src/arash/data: local market data, validation, quality checks, reconciliation and snapshots.
- src/arash/integrations: public read-only market-data adapters.
- src/arash/research: backtests, chronological evaluation, robustness and research diagnostics.
- src/arash/risk: explicit risk inputs, sizing and exposure checks.
- src/arash/paper: simulated broker, paper order workflow and execution scenarios.
- src/arash/storage: local SQLite persistence.
- src/arash/reporting: report and provenance utilities.

The current branch contains an initial real-time public order-book stream and market-quality observations, alongside research, risk and paper-simulation foundations. A resilient multi-market event runtime, order-book-aware execution, exchange order routing, venue reconciliation and production-grade monitoring remain future implementation milestones. Current public-market connectors are read-only; the branch should not be assumed to submit live orders.

## Performance principles

Throughput alone is not the objective. ARASH should optimize for correct state transitions, low avoidable latency, bounded resource use, deterministic replay where feasible, explainable rejection reasons, operational recovery, and measured execution quality. Optimize after representative profiling; do not sacrifice risk controls or accounting integrity for a headline latency number.
