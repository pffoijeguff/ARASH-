# Risk Controls and Safety Boundary

## Operating mode

ARASH Foundation 30.0.0 is documented as an offline research and paper-simulation package. Its recorded tests did not submit live orders, and the snapshot does not provide validated live-order execution. This is a core boundary, not a temporary configuration to switch on by changing a flag.

## Risk areas represented in the reference snapshot

### Position sizing

Risk sizing evaluates proposed quantity against configured trade-risk limits and other constraints, including position-size limits, aggregate exposure, and available simulated cash. Calculation outputs depend on the supplied account values, marks, stop assumptions, and policy parameters. They are not guarantees against loss or gaps.

### Portfolio exposure

Exposure controls constrain simulated position or portfolio allocation. Results should disclose the valuation currency and assumptions. The reference reports make explicit when foreign-exchange conversion is disabled and when valuation uses caller-supplied marks rather than fetched market prices.

### Daily loss and drawdown

Daily-loss and peak-to-trough drawdown controls can block additional exposure when configured thresholds are reached or breached. Correct use depends on a valid baseline, consistent time-zone rules, and current valuations. A limit breach should be visible in the report and should not be silently reset.

### Mark freshness

Stale valuation marks can distort position value, equity, exposure, and risk. Risk-sensitive workflows should flag or block decisions that rely on marks older than the configured threshold. The source and timestamp of marks should be retained.

### Account kill switch

The 29.0.0 change record documents a safety behavior: an active account kill switch blocks new BUY exposure while still allowing a valid SELL to reduce or close an existing long position. The switch remains active after a sell and requires an explicit, reasoned manual reset before BUY orders can resume. This behavior has regression-test evidence in the reference history; it is still a paper/research control and is not a claim about live exchange execution.

## Safe research practices

1. Use synthetic data or authorized local datasets for examples and tests.
2. Keep exchange credentials, API keys, account identifiers, local ledgers, and private datasets out of public commits.
3. Do not embed secrets in source code, test fixtures, issue reports, or generated documentation.
4. Preserve failed and incomplete checks in reports; do not edit a result to make a gate appear green.
5. Avoid calling a simulated fill a real fill or describing a backtest as a live-trading result.
6. Review schema changes and database migrations against backups or disposable local ledgers.

## What risk controls do not provide

Risk checks cannot eliminate volatility, gaps, slippage, liquidity changes, software defects, bad inputs, model error, strategy overfitting, or future losses. Risk thresholds are policy choices, not universal guarantees. Backtest and paper-simulation results may diverge materially from real venues.

## Live trading

No live-trading activation path is documented here. Any future proposal to add live execution must be treated as a separate, high-risk engineering project with an explicit threat model, credential isolation, venue-specific validation, durable order-state reconciliation, kill-switch testing, human approval, and an independently reviewed release process. It must not be inferred from research capability or paper-broker support.

## Disclosure

ARASH is a software and research project, not investment advice. Users are responsible for lawful data use, operational controls, and any decisions based on outputs.