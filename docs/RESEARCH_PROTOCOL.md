# Research Protocol

ARASH reports should be treated as evidence about a specified dataset and model configuration, not as predictions of future returns.

## Minimum protocol

1. Record dataset identity, source, timestamp convention, timezone, and content digest.
2. Validate schema, ordering, duplicates, missing intervals, outliers, and session boundaries before research.
3. Keep feature construction and parameter selection isolated from the final evaluation window.
4. Prefer walk-forward or other chronological out-of-sample evaluation; do not randomly shuffle time series.
5. Model fees, spread, slippage, liquidity and capacity as explicit assumptions, and perform sensitivity analysis.
6. Compare against a declared benchmark, including simple baselines such as buy-and-hold where appropriate.
7. Record the full tested parameter family and account for multiple comparisons when interpreting evidence.
8. Preserve code version, settings, dataset digest, and output manifest so a run can be reproduced.
9. State data and execution limitations alongside headline metrics.

## Interpretation

A backtest can be affected by data leakage, selection bias, sparse samples, regime shifts, unmodeled costs, and differences between simulated and real execution. Passing an internal audit is not proof of an investable edge. Statistical evidence from a limited test must be independently validated before any strong conclusion is drawn.
