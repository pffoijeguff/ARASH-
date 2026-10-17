# Research Protocol and Evidence Standards

## Objective

ARASH should make quantitative experiments reproducible and keep the limits of their evidence explicit. This protocol is a research standard, not a claim that any strategy is profitable.

## 1. Define the experiment

Record the dataset identity, symbol and interval, date range, configuration, benchmark, candidate family, evaluation method, and transaction-cost assumptions. Treat material changes as a new experiment rather than silently rewriting the old one.

## 2. Validate the inputs

Check for malformed values, duplicate or unordered timestamps, gaps, stale data, mixed instruments or intervals, and unclear provenance. Preserve warnings in reports and block runs when required assumptions are violated.

## 3. Prevent temporal leakage

Use chronological splits. Keep evaluation windows separate from strategy selection, tuning, and transformations that learn from data. A focused look-ahead check only supports the specific behavior it tests; it is not universal proof that all leakage is absent.

## 4. Evaluate out of sample

Prefer chronological walk-forward evaluation to a single favorable in-sample result. Document fold boundaries, overlap, aggregation method, and sample limitations. Inadequate evidence should remain inadequate rather than being converted into confidence.

## 5. Compare fairly

Use a declared benchmark where appropriate. Explain gross versus net returns, cash treatment, exposure assumptions, and evaluation periods. Comparisons are misleading when the strategy and benchmark use materially different assumptions.

## 6. Model execution friction

Challenge results with relevant fees, spread, slippage, liquidity, capacity, and partial-fill assumptions. Bar-based simulations cannot fully reproduce order-book state, latency, queue position, or actual venue behavior.

## 7. Account for selection bias

Disclose how many candidates were tested and how the candidate family was formed. Where supported and appropriate, use multiple-testing corrections or selection-bias diagnostics. Do not present the best selected result as if it had been chosen independently of all other trials.

## 8. Preserve evidence and limitations

Keep machine-readable reports, experiment settings, dataset identity, and relevant test evidence together. Clearly distinguish synthetic examples from market observations. A file hash can detect byte changes, but it does not prove the source or truth of the file.

## Version 28.0.0 change of note

The release notes describe a position-sizing correction: existing exposure in the same instrument is deducted when sizing an additional BUY, and same-instrument exposure is validated against total portfolio exposure. The archive records regression tests for these cases.

## Non-negotiable rule

**A backtest, a passing software test, a paper fill, or a risk diagnostic does not prove profitability and does not authorize live trading.**
