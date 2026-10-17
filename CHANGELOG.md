# Changelog

## Unreleased — research-led platform development

- Reframed the public project positioning around research-driven quantitative trading, execution-aware design and risk-first automation rather than an offline-only identity.
- Documented the target event-driven research-to-execution architecture and the distinction between current capabilities and future milestones.
- Added research foundations based on literature about backtest overfitting, multiple testing, time-series validation, crypto microstructure and market-access risk controls.
- Expanded the roadmap around point-in-time data, leakage-resistant validation, execution economics, portfolio-level risk, online runtime and operational resilience.

This is ongoing development, not a verified production release. Tests and the full release gate remain skipped for the current source-transfer phase.

## 28.0.0 — 2026-10-16

- Corrected per-instrument position-cap sizing so current exposure in the same instrument is deducted before sizing an additional BUY.
- Updated the paper broker to pass marked same-instrument exposure to the risk engine.
- Exposed the current-position-exposure input in the advisory risk-check command.
- Added validation for inconsistent same-instrument and total-portfolio exposure values.
- Translated end-user research explanations in selected quantitative-review modules to English without changing their algorithms.

This is a risk-control and localization release, not evidence of trading profitability. Execution remains simulation-only.
