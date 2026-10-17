# CLI Reference

All commands run locally unless \`market-fetch\` is explicitly requested. Public market fetching is read-only. No CLI command submits an exchange order.

## Data quality

Audit a CSV before research:

    python -m arash csv-health sample_data/research_demo_320.csv

Use a reference time to make freshness checks reproducible:

    python -m arash csv-health sample_data/research_demo_320.csv --at 2026-10-17T12:00:00Z

Strictly validate rows:

    python -m arash csv-validate sample_data/research_demo_320.csv

## Backtesting

Run a predeclared baseline:

    python -m arash backtest sample_data/research_demo_320.csv --strategy buy-hold
    python -m arash backtest sample_data/research_demo_320.csv --strategy sma-crossover --short-window 5 --long-window 20

Adjusting multiple parameters after looking at results creates selection bias. Use a holdout or robustness report, and disclose the full candidate family:

    python -m arash evaluate sample_data/research_demo_320.csv --strategy sma-crossover --train-fraction 0.70
    python -m arash robustness sample_data/research_demo_320.csv --strategy buy-hold
    python -m arash research-grid sample_data/research_demo_320.csv --strategies buy-hold sma-crossover --short-windows 3 5 --long-windows 15 20 --max-candidates 20

## Market diagnostics

    python -m arash regime-analysis sample_data/research_demo_320.csv --lookback 20
    python -m arash market-intelligence sample_data/research_demo_320.csv --output artifacts/market-intelligence.json

Market intelligence and regime classifications are descriptive heuristics, not predictions or trade signals.

To compare two already-saved market reports:

    python -m arash market-watch artifacts/previous-report.json --previous-report artifacts/older-report.json

## Risk sizing

Calculate a hypothetical spot position size:

    python -m arash risk-check --equity 10000 --cash 10000 --entry-price 100 --stop-price 95 --current-exposure 0 --current-position-exposure 0

All monetary inputs must use the same currency. Risk outputs depend on caller-supplied marks, costs and stop assumptions.

## Execution simulation

    python -m arash execution-simulate sample_data/research_demo_320.csv --side buy --quantity 10 --submitted-at 2026-10-12T02:00:00Z
    python -m arash execution-stress sample_data/research_demo_320.csv --side buy --quantity 10 --submitted-at 2026-10-12T02:00:00Z

The simulator uses a completed prior candle's volume as a conservative capacity reference. OHLCV does not reveal queue position, order-book depth, or actual fills.

## Output files

Most analysis commands support \`--output path.json\`. JSON reports document input hashes where supported and include explicit limitations. A content hash identifies exact bytes; it does not authenticate the data provider.
