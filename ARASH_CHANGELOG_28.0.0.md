# ARASH Foundation 28.0.0

## Risk sizing correction

- Fixed per-instrument position-cap sizing so existing exposure in the same instrument is deducted before sizing an additional BUY.
- Paper broker now passes marked same-instrument exposure into the risk engine; the advisory `risk-check` CLI exposes `--current-position-exposure` for the same contract.
- Added validation that same-instrument exposure cannot exceed total portfolio exposure.
- Added regression tests for incremental-position cap enforcement and invalid exposure inputs.

This is a software risk-control correction, not evidence of trading profitability. ARASH remains research/paper-only.
