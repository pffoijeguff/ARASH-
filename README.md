# ARASH — Adaptive Quantitative Trading Intelligence

**Research-grade thinking. Execution-aware design. Risk-first automation.**

ARASH is an ambitious quantitative-trading platform being engineered to connect market intelligence, rigorous strategy research, portfolio risk, execution modelling, and operational controls in one coherent system. Its goal is not to generate the largest number of signals. Its goal is to make every trading decision explainable, measurable, reproducible, and accountable to real market constraints.

ARASH is designed to grow beyond a collection of indicators or a candle-loop script: market data is validated before it is trusted; hypotheses are evaluated against chronological evidence; transaction costs and liquidity belong in the decision process; risk checks sit between a strategy and any future execution route; and research runs retain provenance for review and reproduction.

## The ARASH engineering standard

- **Market-aware intelligence:** market-data quality, regime context, volatility and liquidity diagnostics inform research instead of treating every candle as equally reliable.
- **Research discipline:** chronological evaluation, explicit benchmarks, parameter-family accounting, robustness scenarios and reproducible run manifests are first-class concerns.
- **Execution realism:** fees, spreads, slippage, latency, partial fills and market impact are design requirements—not afterthoughts hidden behind a headline return.
- **Risk before routing:** position sizing, exposure limits, drawdown controls, order validation, stale-data protection and independent stop mechanisms belong in the control path.
- **One auditable lifecycle:** data provenance, strategy configuration, risk decisions, simulated fills, accounting and reports should be traceable end to end.
- **Extensible by design:** the architecture is intended to support multiple strategies, assets, venues and model families without coupling signal generation to order handling.

## What the current source branch contains

| Capability | Current source area |
| --- | --- |
| Market-data validation, public candles and live order-book streaming | src/arash/data and src/arash/integrations |
| Live order-book and trade streams with rolling flow features | src/arash/data/streaming.py and src/arash/research/streaming_features.py |
| Microprice, spread, displayed depth imbalance, reported-side trade notional imbalance and rolling VWAP | Live microstructure feature engine |
| Baseline backtests and chronological holdout evaluation | src/arash/research |
| Robustness, candidate-family, CSCV/PBO and block-bootstrap uncertainty diagnostics | src/arash/research |
| Market-regime and descriptive market-intelligence reports | CLI and research modules |
| Explicit position sizing and risk diagnostics | src/arash/risk |
| Persistent paper-account records and safety controls | src/arash/paper and src/arash/storage |
| Execution-cost scenarios, stress cases and research manifests | paper, research and reporting modules |

Historical replay and local research are controlled modes within the engineering toolkit; they are not the definition or long-term ambition of ARASH. Online market-data ingestion is now represented by an initial public order-book stream with bounded reconnects and descriptive microstructure measurements. Execution-aware decisioning and a carefully controlled path from research to paper operation remain central architectural objectives. Production order routing and the complete real-time operational stack remain development milestones, not features to assume are already available in this branch.

## Quick start

Requires Python 3.12 or newer.

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install .
    python -m arash --help

Windows PowerShell activation:

    .\.venv\Scripts\Activate.ps1

Useful starting commands:

    python -m arash csv-validate sample_data/research_demo_320.csv
    python -m arash backtest sample_data/research_demo_320.csv --strategy buy-hold
    python -m arash market-intelligence sample_data/research_demo_320.csv
    python -m arash return-stats sample_data/return_stats_demo.json --iterations 2000 --block-length 5

For a live read-only public order-book stream (requires the optional WebSocket dependency):

    python -m pip install ".[marketstream]"
    python -m arash market-stream --symbol BTCIRT --max-events 10 --depth-levels 10

The streaming command subscribes to Nobitex's public order-book and public-trades channels over one WebSocket connection and bootstraps the initial book from the public REST snapshot. Each event is enriched with bounded rolling trade-flow features. It reports market observations only and does not submit orders.

Browse the [CLI reference](docs/CLI_REFERENCE.md), [architecture](docs/ARCHITECTURE.md), [live market microstructure guide](docs/MARKET_MICROSTRUCTURE.md), [research protocol](docs/RESEARCH_PROTOCOL.md), [research foundations](docs/RESEARCH_FOUNDATIONS.md), and [risk-control principles](docs/RISK_AND_SAFETY.md).

## The next-generation target

ARASH is being developed toward a cohesive research-to-execution architecture with event-driven market updates; point-in-time and multi-venue data; order-book and liquidity context where available; explicit alpha/model interfaces; portfolio-aware position targets; independent pre-trade risk approval; realistic exchange-specific execution models; durable order/fill/position accounting; live health and drift monitoring; and auditable emergency-stop controls.

These are engineering objectives, not a claim that every capability is already implemented. The roadmap prioritizes evidence quality and operating discipline alongside predictive sophistication: a complex model that cannot survive realistic costs, leakage controls and changing market regimes is not a strong trading system.

## Development status

ARASH is under active development. The current source-sync branch may contain defects, incomplete integrations or behavior that changes as implementation proceeds. The repository does not claim a verified production release or demonstrate profitable future performance. Do not connect it to real-money execution on the assumption that this branch is production-ready.

## License

An explicit license for external reuse or redistribution has not yet been selected.
