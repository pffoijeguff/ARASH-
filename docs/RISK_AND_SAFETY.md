# Risk Controls and Safety Boundary

## Operating mode

ARASH Foundation 28.0.0 is documented as an offline research and paper-simulation package. Its recorded release checks used no network and submitted no live orders. This repository must not be interpreted as a live trading service.

## Position sizing and portfolio exposure

The 28.0.0 change record documents a correction to incremental position sizing: existing exposure in the same instrument is accounted for before sizing an additional BUY. The reference tests also cover rejection of same-instrument exposure that exceeds total portfolio exposure.

Position limits depend on account values, valuation marks, policy parameters, and assumptions. They are not guarantees against gaps, liquidity changes, or losses.

## Mark freshness and stress diagnostics

Stale valuation marks can distort position value, equity, and exposure. Risk-sensitive workflows should retain mark timestamps and apply configured freshness limits. Portfolio stress analysis is a diagnostic tool; its scenarios are not predictions of future prices or maximum-loss guarantees.

## Paper execution

Paper accounts and orders use simulated state. A paper fill is not a real exchange fill, and local simulated balances are not real funds. Reports should make this boundary explicit.

## Safe research practices

1. Use synthetic data or authorized local datasets for examples and tests.
2. Keep exchange credentials, API keys, account identifiers, local ledgers, and private datasets out of public commits.
3. Do not embed secrets in source code, test fixtures, issue reports, or generated documentation.
4. Preserve failed and incomplete checks in release reports.
5. Review database migrations against disposable test databases or backups.
6. Do not infer profitability from a backtest or infer production safety from a test count.

## Live trading

The reference snapshot is research/paper-only. Any future live-execution proposal would require a separate threat model, credential isolation, venue-specific validation, durable order-state reconciliation, kill-switch testing, human approval, and independent release review. Live trading must not be enabled implicitly by a research feature.

## Disclosure

ARASH is a software and quantitative-research project, not investment advice. Users remain responsible for lawful data use, operational controls, and decisions based on any outputs.
