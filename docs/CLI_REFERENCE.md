# CLI Reference

ARASH separates online public-market data retrieval from deterministic research and paper simulation. Public market fetching is read-only; this development branch has no production order-routing adapter.

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

## Live public order-book stream

Install the optional streaming dependency:

    python -m pip install ".[marketstream]"

Receive ten snapshots for one market, showing ten levels per side:

    python -m arash market-stream --symbol BTCIRT --max-events 10 --depth-levels 10

The command connects to the documented public WebSocket endpoint, subscribes to `public:orderbook-SYMBOL`, and requests a bounded initial snapshot from `GET /v3/orderbook/SYMBOL`. No API key is needed for this public channel. The feed emits validated JSON snapshots with bid/ask prices and sizes, midpoint, microprice, spread in basis points, receive lag, and top-depth quantity imbalance. Output depth is bounded by `--depth-levels` (1–500). Use `--max-events 0` to continue until interrupted; `--max-reconnects` caps consecutive reconnect attempts.

The provider publishes order-book messages when the book changes, so quiet markets may have long gaps. The initial REST snapshot gives the stream a starting book; the CLI does not infer a buy/sell recommendation from microstructure fields. Timestamp ordering and provider behavior still need verification before the feed is used as an input to another system.

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

Estimate candidate-selection instability with Combinatorial Symmetric Cross-Validation (CSCV). The input JSON must contain aligned per-period return series in fractions, net of the cost assumptions under study:

    python -m arash pbo-audit sample_data/pbo_demo_candidate_returns.json --blocks 8 --output artifacts/pbo-audit.json

The diagnostic reports how often an in-sample-selected candidate ranks below the median on complementary out-of-sample blocks. It is not a future-loss probability, does not replace an untouched chronological holdout, and is not the Deflated Sharpe Ratio. The included demo series are synthetic examples, not observed market returns.

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
