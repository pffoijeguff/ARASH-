# Risk and Safety Boundaries

ARASH Foundation 28.0.0 is intended for research and paper simulation only. It is not financial advice and cannot guarantee capital preservation or trading profitability.

## Execution boundary

- The project does not support live order submission.
- Public market-data adapters are read-only and opt-in.
- A paper fill is a model output, not confirmation of an exchange fill.
- A simulated stop price is not guaranteed to be a real fill price; gaps and slippage can exceed an assumed risk budget.

## Risk controls

- Risk sizing depends on caller-supplied inputs and the declared policy.
- Existing exposure in the same instrument must be accounted for before sizing an additional position.
- Portfolio exposure, daily loss, drawdown, and instrument caps are diagnostic controls, not guarantees.
- Stale or incorrect marks, baselines, and cost assumptions can invalidate a risk estimate.

## Research limitations

- Historical results and synthetic fixtures do not establish future performance.
- Walk-forward, prefix-invariance, bootstrap, sign-flip, and multiple-testing checks depend on assumptions and available sample size.
- Data hashes support byte-level integrity checks but do not prove provider authenticity or data correctness.
- Cross-source agreement does not establish that either source is accurate.
- A reproducible report establishes what was run under declared inputs; it does not prove that the chosen model is economically useful.
