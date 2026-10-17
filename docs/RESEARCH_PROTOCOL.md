# Research Protocol and Evidence Standards

## Objective

This protocol describes how ARASH should evaluate a trading hypothesis without overstating what the evidence proves. Research should be reproducible, temporally sound, cost-aware, and explicit about incomplete checks.

## 1. Freeze the experiment definition

Before evaluation, record the dataset identity, symbol and interval where applicable, data range, configuration or experiment fingerprint, candidate family, benchmark, evaluation method, random seeds when used, and transaction-cost assumptions. Avoid changing the candidate universe after examining the evaluation results without recording the change as a new experiment.

## 2. Validate the input series

Run structural and temporal quality checks before backtesting. Investigate duplicates, unordered timestamps, invalid values, mixed instruments or intervals, unexplained gaps, stale data, and incomplete provenance. Preserve warnings in the report. If the input violates required assumptions, block the experiment rather than treating the data as clean.

## 3. Prevent temporal leakage

Use chronological splits. Keep the evaluation window separate from strategy selection, parameter tuning, and transformations that can learn from future values. Include a focused look-ahead audit when the method supports it. Passing one targeted audit is evidence for that check only; it is not a universal proof that every form of leakage is absent.

## 4. Use out-of-sample evaluation

Prefer repeated, chronological walk-forward evaluation over one favorable in-sample score. State how folds are defined, whether their test windows overlap, and how results are aggregated. Report the number of usable folds. If the evidence is too small or structurally insufficient, preserve that limitation in the result instead of manufacturing confidence.

## 5. Compare with a defensible baseline

Use a declared benchmark, such as buy-and-hold where appropriate, under compatible assumptions. Explain whether returns are gross or net of costs, how cash and exposure are treated, and which periods are included. A result cannot be interpreted correctly if the strategy and baseline are evaluated under materially different assumptions.

## 6. Model execution friction

Challenge results with relevant fee, spread, slippage, market-impact, liquidity, capacity, and partial-fill assumptions. Where possible, run multiple cost scenarios and disclose sensitivity. Bar-based simulations are approximations; they cannot fully reproduce order-book state, venue latency, queue position, or real fill behavior.

## 7. Account for selection bias and multiple testing

Disclose the size and construction of the candidate family. When appropriate and available, use multiple-testing corrections or diagnostics such as Holm–Bonferroni, CSCV/PBO, or deflated-Sharpe methods. Report the method, inputs, and interpretation. Do not present a single unadjusted best result as if it had been selected independently of all other trials.

## 8. Bind the evidence

The 30.0.0 reference snapshot can assemble a research dossier from local JSON reports. It inspects dataset/configuration provenance, temporal out-of-sample evidence, a recognized look-ahead check, selection-bias or multiple-testing evidence, transaction-cost robustness, and offline/input-quality guardrails. It also binds report names, sizes, and SHA-256 identities; optional dataset or protocol files can be linked and verified when supplied.

The recorded implementation applies a maximum of 12 report inputs and a 10 MiB per-report size limit. Missing evidence remains `INCOMPLETE`. Contradictory dataset identities, invalid temporal structure, failed look-ahead evidence, explicit input-quality failures, or unsafe-execution markers can lead to `BLOCKED`.

## 9. Interpret the status correctly

- `RESEARCH_REVIEWABLE`: the configured evidence checklist is complete enough for human research review.
- `INCOMPLETE`: required evidence is missing, unavailable, or not fully verified.
- `BLOCKED`: a recognized blocking condition was found.

These statuses describe the evidence checklist, not strategy profitability. A `PASS` from the verifier confirms only the integrity checks it actually performed. A SHA-256 hash does not prove file origin, author identity, lawful data rights, or the economic value of a strategy.

## 10. Publish the limits with every result

Research reports should disclose the input identity, test methodology, candidate-selection process, costs, sample limitations, failed or unavailable checks, benchmark, and the precise scope of every conclusion. Synthetic demonstration data must be labeled synthetic and must never be shown as live-market performance.

## Non-negotiable rule

**No research report, backtest score, or evidence-dossier status automatically authorizes live trading.** The public ARASH Foundation 30.0.0 reference snapshot remains an offline research and paper-simulation package.