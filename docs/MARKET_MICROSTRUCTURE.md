# ARASH Live Market Microstructure

ARASH's public market stream is an online market-observation component for order-book and reported trade events. It provides validated snapshots that downstream research and monitoring components can consume. It intentionally does not convert these observations directly into buy/sell recommendations.

## Data lifecycle

1. Fetch a bounded initial public REST snapshot from the documented v3 order-book endpoint.
2. Connect to the public WebSocket endpoint and subscribe to the public order-book and public-trades channels for the selected symbol.
3. Parse full order-book publications and reported public trade prints, validate prices, volumes and timestamps, sort bid/ask levels, and reject malformed, non-finite, crossed or locked books.
4. Emit structured JSON observations with exchange timestamp, local receive timestamp and the provider publication offset when available.
5. Reconnect under a bounded backoff after a stream failure; ignore snapshots that arrive with an exchange timestamp older than the last delivered snapshot.

The current adapter uses the public Nobitex endpoint and public order-book/trades channels only. Its streaming path accepts no API credentials and exposes no order-submission methods. Official provider documentation:
- [Nobitex public market-data API](https://github.com/nobitex/docs-api/blob/master/source/includes/_market_data.md)
- [Nobitex WebSocket protocol and public channels](https://github.com/nobitex/docs-api/blob/master/source/includes/_websocket.md)

## Snapshot fields

### Best bid, best ask and midpoint

- **Best bid** is the highest displayed purchase price.
- **Best ask** is the lowest displayed sale price.
- **Midpoint** is `(best_bid + best_ask) / 2`. It is a reference metric, not a guarantee of an executable price.

### Spread

The quoted spread is `best_ask - best_bid`. The relative spread in basis points is:

`spread_bps = (best_ask - best_bid) / midpoint * 10,000`

A wider spread can indicate greater immediate trading cost or thinner liquidity, but it is not sufficient on its own to infer direction.

### Microprice

The reported size-weighted microprice uses the best quote prices and displayed sizes:

`microprice = (best_ask * best_bid_quantity + best_bid * best_ask_quantity) / (best_bid_quantity + best_ask_quantity)`

This is a descriptive order-book statistic, not a reliable stand-alone forecast. Displayed size can change quickly, and spoofing, cancellations, queue position and hidden liquidity are not fully represented by the snapshot.

### Top-depth quantity imbalance

For the number of levels requested by `--depth-levels`, ARASH computes:

`imbalance = (sum_bid_quantity - sum_ask_quantity) / (sum_bid_quantity + sum_ask_quantity)`

The range is ordinarily from -1 to +1 for non-negative quantities. Positive values mean more displayed quantity on the bid side of the selected depth; negative values mean more on the ask side. It does **not** mean price will rise or fall. The current measurement sums displayed quantities, not the quote-currency notional at each price.

### Rolling reported-trade flow

The stream also subscribes to the public `public:trades-SYMBOL` channel. For the configured rolling window (`--flow-window-seconds`, from 5 to 3600 seconds), the feature engine reports:

- number of retained trade events;
- reported buy and sell volume in base units and quote notional;
- difference between reported buy and sell quote notional;
- normalized reported-side notional imbalance, bounded between -1 and +1 when the total notional is positive;
- volume-weighted average trade price over the window;
- latest trade timestamp and event-time window boundaries.

These fields use the exchange's reported `type` value; ARASH does not claim it proves the aggressor side or predicts the next price movement. The rolling state is bounded by both window age and a maximum event count. Trade prints are only observed after the live subscription begins; the public book REST bootstrap is not a historical trade feed.

### Timestamps and provider offset

- `exchange_timestamp` comes from the provider's order-book update timestamp.
- `received_at` is captured on the client.
- `feed_lag_ms` reports non-negative observed delay; `clock_skew_ms` separately exposes an exchange timestamp ahead of the local receive time.
- `update_offset` is included when supplied by the streaming protocol. Full sequence-gap detection and resynchronization remain roadmap work; the field should not be treated as proof that no updates were missed.

Local clock synchronization, network delay, provider caching and channel activity can affect these diagnostics.

## Data and execution limits

A public order book is a time-stamped view of displayed liquidity, not a complete representation of the market. It does not by itself model hidden orders, order priority, cancellation races, queue position, execution fees, partial fills or market impact. The provider may publish only when the book changes; a quiet channel does not imply a frozen or healthy price. ARASH therefore bootstraps from a REST snapshot and keeps order-book observations descriptive.

The current command supports one symbol per process and caps the emitted depth to a selected number of levels. Cross-venue normalization, multi-market orchestration, durable high-rate event storage, gap recovery, drift monitoring and market-impact-calibrated execution are further engineering milestones.

## Command

Install the optional dependency and stream ten events:

    python -m pip install ".[marketstream]"
    python -m arash market-stream --symbol BTCIRT --max-events 10 --depth-levels 10

The output reports observations only. It does not issue trading recommendations or submit orders.

The same WebSocket connection subscribes to the documented `public:trades-SYMBOL` channel. Each event is enriched by a bounded rolling window with reported buy/sell volume and quote notional, reported-side notional imbalance, rolling trade VWAP, and the latest order-book context when available. The reported-side fields are kept explicitly descriptive; this does not establish buyer/seller aggressor intent or a profitable trading edge.
