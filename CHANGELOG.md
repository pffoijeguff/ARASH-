# Changelog

## 28.0.0 — 2026-10-16

- Corrected per-instrument position-cap sizing so current exposure in the same instrument is deducted before sizing an additional BUY.
- Updated the paper broker to pass marked same-instrument exposure to the risk engine.
- Exposed `--current-position-exposure` in the advisory `risk-check` command.
- Added validation for inconsistent same-instrument and total-portfolio exposure values.
- Added regression coverage for incremental position-cap enforcement and invalid exposure inputs.
- Translated end-user research explanations in selected quantitative-review modules to English without changing their algorithms.

This is a risk-control and localization release, not evidence of trading profitability. Execution remains simulation-only.
