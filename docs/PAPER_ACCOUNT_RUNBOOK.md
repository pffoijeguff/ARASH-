# Paper Account Runbook

This document covers a local-only simulated account. It describes no real exchange connection and no live-order workflow.

## 1. Create an account

Use an isolated local database path. Select a currency that matches the quote currency of the instruments you will register:

    python -m arash paper-account-create --db data/demo-paper.sqlite3 --account-id demo --initial-cash 10000 --account-currency IRT

The default \`SIMULATED_UNITS\` currency is a placeholder unit. It is not a claim that the balance is US dollars or any other real currency. FX conversion is disabled.

## 2. Register an instrument

    python -m arash paper-instrument-register --db data/demo-paper.sqlite3 --symbol BTCIRT --base-currency BTC --quote-currency IRT

The instrument quote currency must match the account currency. For example, an account denominated in IRT cannot hold a position priced in USD without a supported conversion mechanism; no conversion mechanism is implemented.

## 3. Review and record the account

Open positions require explicit price marks; the account does not silently fetch prices:

    python -m arash paper-status --db data/demo-paper.sqlite3 --account-id demo --mark BTCIRT 1000000

Record a paper-equity observation for risk baselines:

    python -m arash paper-status --db data/demo-paper.sqlite3 --account-id demo --mark BTCIRT 1000000 --record

The example price is illustrative only and must not be interpreted as current market data.

## 4. Risk audit and circuit breaker

    python -m arash paper-risk-audit --db data/demo-paper.sqlite3 --account-id demo --mark BTCIRT 1000000
    python -m arash paper-risk-stress --db data/demo-paper.sqlite3 --account-id demo --mark BTCIRT 1000000

A risk audit can activate a persistent paper-account kill switch when a configured limit is breached. The stress report is diagnostic and does not by itself mutate that switch.

Clearing an active switch requires a reason and explicit confirmation:

    python -m arash paper-risk-reset --db data/demo-paper.sqlite3 --account-id demo --reason "Reviewed simulated state" --confirm-reset

Do not use reset as a substitute for checking current positions, cash, stale marks, and the reason for the halt.

## 5. Orders are paper-only

The paper broker uses a caller-supplied reference price, local SQLite transactions, and modeled fees/slippage. Short selling, leverage, FX conversion, and live order submission are disabled. BUY requests require an explicit risk policy, stop price, peak-equity observation, and daily-start-equity baseline.

Every result remains a simulation. It does not reflect guaranteed venue liquidity or execution.
