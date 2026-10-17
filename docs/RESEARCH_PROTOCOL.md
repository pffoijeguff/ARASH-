# ARASH Research Protocol

The goal of ARASH research is not to find a configuration with the highest historical return. It is to determine whether a clearly specified hypothesis survives leakage control, meaningful baselines, realistic trading costs, parameter uncertainty and changes in market conditions.

## Minimum evidence contract

Every research run should record:

- dataset source, venue, instrument, time range, timezone and event/receive-time convention;
- data version or content digest, corrections, missing intervals and quality findings;
- code version, feature definitions, strategy/model version, parameters and random seeds where applicable;
- the full number and family of attempted configurations, including failed or discarded candidates;
- benchmark definitions, fees, spread, slippage, liquidity and financing assumptions;
- training, validation and final holdout windows, with a clear separation between them;
- gross and net returns, turnover, exposure, drawdown, tail outcomes and uncertainty measures;
- artifact manifest sufficient to reproduce and review the experiment.

## Validation protocol

1. **Declare the hypothesis first.** Specify the signal, instrument universe, horizon, decision timestamp, expected mechanism and falsifiable alternative.
2. **Validate point-in-time data.** Reject look-ahead, duplicate events, incorrect ordering, stale observations, survivorship-contaminated universes and features unavailable at decision time.
3. **Use time-respecting splits.** Keep a chronological holdout untouched during development. Do not randomly shuffle financial time series.
4. **Purge overlapping information.** Where labels or positions overlap across time, use purging and an embargo appropriate to the label horizon. Investigate CPCV/Combinatorial Purged Cross-Validation where its assumptions fit the question.
5. **Account for selection.** Preserve the full candidate ledger. Report how many alternatives were tried and consider Probability of Backtest Overfitting (PBO), Deflated Sharpe Ratio (DSR), and other multiple-testing controls when interpreting selected results.
6. **Model net execution economics.** Include fees, spread, slippage, latency, partial fills, rejections, market impact, financing/funding and capacity assumptions as relevant to the instrument and venue.
7. **Use meaningful baselines.** Compare with simple predeclared alternatives and benchmark-relative metrics. Complexity must justify itself out of sample.
8. **Stress uncertainty.** Perturb parameters and costs; assess multiple market regimes, volatility/liquidity conditions, tail events and delayed or missed execution.
9. **Repeat without tuning on the final holdout.** Any decision influenced by holdout results consumes that evidence and requires a fresh evaluation set.
10. **Preserve and communicate the result.** Store the manifest, configuration, outputs and limitations. A negative result is a useful result and should not be silently discarded.

## Metrics to report

Where suitable for the data and strategy, report net return and benchmark-relative return, annualized volatility with its assumptions, Sharpe/Sortino with caveats, maximum drawdown, drawdown duration and recovery, turnover, exposure, trade count, hit rate, average win/loss, tail losses, transaction-cost attribution, capacity sensitivity, and uncertainty/selection-bias diagnostics. No single metric should stand in for a complete risk/return profile.

## Machine learning and adaptive models

- Keep feature generation strictly point-in-time and fit preprocessing only on training folds.
- Compare learned models with simple baselines on identical splits and cost assumptions.
- Record training windows, feature versions, hyperparameter searches, artifacts and promotion decisions.
- Monitor feature drift, prediction calibration, regime changes and net performance degradation.
- Treat ensembles and complexity as hypotheses requiring evidence, not as automatic sources of edge.
- Do not infer stable alpha merely from feature importance or in-sample predictive fit.

## Interpretation

Backtests and paper runs are models of specified data and assumptions. They are not promises of future results. Real market impact, fees, liquidity, latency, competition, market regime changes and data quality can erase apparent edges. ARASH should prefer evidence that is reproducible, economically plausible and robust to reasonable stress over a spectacular but fragile backtest.
