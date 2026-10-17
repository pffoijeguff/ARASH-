# CLI Reference

All commands run locally unless \`market-fetch\` is explicitly requested. Public market fetching is read-only. No CLI command submits an exchange order.

## Data quality

Audit a CSV before research:

    python -m arash csv-health sample_data/example_candles.csv --at 2026-10-12T04:00:00+03:30

Strictly validate rows:

    python -m arash csv-validate sample_data/research_demo_320.csv

## Public-data sync and lineage

Fetch a bounded candle history and persist it to a local SQLite database, including its normalized hash and snapshot manifest:

    python -m arash market-sync --db data/market.sqlite3 --symbol BTCIRT --interval 1h --count 100

Reconcile the local ledger and snapshot metadata:

    python -m arash market-reconcile --db data/market.sqlite3

Market retrieval is opt-in. It uses a public read-only endpoint and does not touch trading accounts.

## Backtesting and robustness

Run a predeclared baseline:

    python -m arash backtest sample_data/research_demo_320.csv --strategy buy-hold
    python -m arash backtest sample_data/research_demo_320.csv --strategy sma-crossover --short-window 5 --long-window 20

Review chronological holdout, model assumptions, and perturbations:

    python -m arash evaluate sample_data/research_demo_320.csv --strategy sma-crossover --train-fraction 0.70
    python -m arash quant-audit sample_data/research_demo_320.csv --strategy buy-hold
    python -m arash robustness sample_data/research_demo_320.csv --strategy buy-hold
    python -m arash research-grid sample_data/research_demo_320.csv --strategies buy-hold sma-crossover --short-windows 3 5 --long-windows 15 20 --max-candidates 20

Do not declare a winning configuration based only on a grid maximum. Disclose the full tested candidate family and reserve separate chronological data for follow-up analysis.

## Market diagnostics

    python -m arash regime-analysis sample_data/research_demo_320.csv --lookback 20
    python -m arash market-intelligence sample_data/research_demo_320.csv --output artifacts/market-intelligence.json

Market intelligence and regime classifications are descriptive heuristics, not predictions or trade signals.

To compare saved market reports:

    python -m arash market-watch artifacts/current-report.json --previous-report artifacts/previous-report.json

The command emits observable state changes only. It does not generate buy/sell/hold recommendations.

## Risk sizing

Calculate a hypothetical spot position size:

    python -m arash risk-check --equity 10000 --cash 10000 --entry-price 100 --stop-price 95 --current-exposure 0 --current-position-exposure 0

All monetary inputs must use the same currency. Risk outputs depend on caller-supplied marks, costs and stop assumptions.

## Execution simulation

    python -m arash execution-simulate sample_data/research_demo_320.csv --side buy --quantity 10 --submitted-at 2026-10-12T02:00:00Z
    python -m arash execution-stress sample_data/research_demo_320.csv --side buy --quantity 10 --submitted-at 2026-10-12T02:00:00Z

For multiple independent what-if simulations, provide a JSON file with an \`orders\` array:

    python -m arash execution-batch sample_data/research_demo_320.csv sample_data/event_execution_demo_orders.json

Batch requests are simulated independently against the same candle series. Their liquidity capacity is not shared across requests; this is not an aggregate venue fill model.

## Artifact provenance

Generate a manifest for a saved JSON report:

    python -m arash research-manifest artifacts/market-intelligence.json --output artifacts/manifest.json

The manifest records hashes for reproducibility. A content hash identifies exact bytes; it does not authenticate a data provider.

Most analysis commands support \`--output path.json\`. A report describes only the supplied data and assumptions.
