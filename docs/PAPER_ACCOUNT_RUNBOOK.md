# Paper Account Runbook

This document covers a local-only simulated account. It describes no real exchange connection and no live-order workflow.

## 1. Create an account

Use an isolated local database path:

    python -m arash paper-account-create --db data/demo-paper.sqlite3 --account-id demo --initial-cash 10000

The default \`SIMULATED_UNITS\` account currency is a placeholder unit, not a claim that the balance is US dollars or any other real currency.

## 2. Register an instrument

For a denomination-aware account, register the base and quote currency explicitly:

    python -m arash paper-instrument-register --db data/demo-paper.sqlite3 --symbol BTCIRT --base-currency BTC --quote-currency IRT

The instrument's quote currency must match the account currency. FX conversion is not implemented.

## 3. Review the account

Positions require explicit price marks; the account does not silently fetch prices:

    python -m arash paper-status --db data/demo-paper.sqlite3 --account-id demo --mark BTCIRT 1000000

Persist an equity observation when using paper risk audits:

    python -m arash paper-status --db data/demo-paper.sqlite3 --account-id demo --mark BTCIRT 1000000 --record

The example mark is illustrative only and must not be interpreted as a current market price.

## 4. Risk audit and circuit breaker

    python -m arash paper-risk-audit --db data/demo-paper.sqlite3 --account-id demo --mark BTCIRT 1000000
    python -m arash paper-risk-stress --db data/demo-paper.sqlite3 --account-id demo --mark BTCIRT 1000000

A risk audit can activate a persistent paper-account kill switch when a configured limit is breached. The stress report is diagnostic and does not by itself mutate the kill switch.

Clearing an active switch requires a reason and explicit confirmation:

    python -m arash paper-risk-reset --db data/demo-paper.sqlite3 --account-id demo --reason "Reviewed simulated state" --confirm-reset

Do not use reset as a substitute for checking current positions, cash, stale marks, and the cause of the halt.

## 5. Orders are paper-only

The paper broker uses a caller-supplied reference price, local SQLite transactions, and modeled fees/slippage. Short selling, leverage, FX conversion, and live order submission are disabled. Buy requests require an explicit stop, peak-equity baseline and daily-start-equity baseline so the risk gate has the necessary assumptions.

Every paper result remains a simulation. It does not reflect guaranteed venue liquidity or execution.
