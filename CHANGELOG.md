# Changelog

Notable changes are listed here. Version numbers refer to the recorded ARASH Foundation reference snapshots; they do not imply that the source for that version has been released from this GitHub repository.

## ARASH Foundation 30.0.0 — 2026-10-16

### Added

- Research Evidence Engine: assemble a sealed dossier from up to 12 local JSON research reports.
- Strict JSON parsing, bounded report inputs of 10 MiB per report, and SHA-256 identities for supplied artifacts.
- Evidence checks for dataset and configuration provenance, chronological out-of-sample validation, recognized look-ahead checks, multiple-testing or selection-bias diagnostics, transaction-cost robustness, and offline/input-quality guardrails.
- `arash verify-research-evidence` to verify the dossier and the exact name, size, and bytes of supplied report artifacts, with optional dataset/protocol file linkage.
- Regression coverage for missing evidence, mismatched datasets, failed audits, unsafe markers, malformed reports, tampering, and CLI behavior.

### Verification status

- 310 automated tests reported passing across 10 isolated groups.
- 12 of 12 local smoke checks reported passing; no live orders were submitted.
- Compilation, wheel integrity, and isolated installation/import reported passing.
- Ruff remained unavailable; Python 3.12 and hosted CI were not verified.
- Overall release gate remained `INCOMPLETE` with 25 checks passed, 0 failed, and 1 incomplete.

### Limits

`RESEARCH_REVIEWABLE` means only that the configured evidence checklist passed. It is not proof of profitability, future returns, live-execution safety, report-author authenticity, or trading authorization. The reference snapshot remains offline-only.

## Documentation publication — 2026-10-17

- Expanded the public project overview and documented the logical architecture, research protocol, risk boundary, release limitations, roadmap, contribution expectations, and security-reporting guidance.
- Recorded explicitly that the source archive has not yet been synchronized into this repository and that archive-level test results are not GitHub-tree CI results.