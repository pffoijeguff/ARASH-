# Changelog

Version numbers refer to the corresponding ARASH Foundation source snapshots. A snapshot version does not imply that the source has already been synchronized into this GitHub repository.

## ARASH Foundation 28.0.0 — 2026-10-16

### Risk sizing correction

- Fixed per-instrument position-cap sizing so existing exposure in the same instrument is deducted before sizing an additional BUY.
- The paper broker passes marked same-instrument exposure into the risk engine.
- The advisory `risk-check` CLI exposes `--current-position-exposure`.
- Added validation that same-instrument exposure cannot exceed total portfolio exposure.
- Added regression tests for incremental-position cap enforcement and invalid exposure inputs.

### Recorded verification

- 301 tests passed across 10 pytest groups.
- 11 of 11 local smoke checks passed.
- Python compilation, wheel integrity, and isolated install/import passed in the recorded environment.
- Ruff was unavailable.
- Python 3.12 and hosted CI were not independently verified.
- Overall release gate: `INCOMPLETE` — 24 passed, 0 failed, 1 incomplete.

### Documentation preparation

- Updated the public project overview and documentation to describe the supplied 28.0.0 archive.
- Explicitly documented that source synchronization into this GitHub repository remains outstanding.

### Limits

These checks validate software behavior in the recorded environment. They do not establish trading profitability, guarantee future results, or authorize live trading.
