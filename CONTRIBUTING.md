# Contributing

Thank you for helping improve ARASH Foundation. Contributions should make research more reproducible, risks clearer, and validation stronger.

## Before opening a change

1. Keep the project offline-first and paper-only; do not add live-order submission.
2. Prefer small, testable changes with clear assumptions and explicit failure handling.
3. Add regression tests for behavior changes and update documentation when user-facing behavior changes.
4. Do not commit secrets, local databases, private datasets, generated build output, or real account data.
5. Do not present backtest output as a return forecast or as proof of a profitable trading edge.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/release_gate.py --output artifacts/release-gate-local.json
```

Use the equivalent virtual-environment activation command for your operating system.

## Pull requests

Describe the motivation, implementation, tests executed, and remaining limitations. Include synthetic or anonymized examples only. CI must pass before a change is considered ready to merge.
