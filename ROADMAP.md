# Roadmap

This roadmap prioritizes reproducibility, defensive controls, and verifiable releases over adding execution capability.

## Immediate: release verification

- [ ] Run the complete release gate locally from a clean environment on Python 3.12 and 3.13.
- [ ] Install Ruff and resolve any lint findings.
- [ ] Verify hosted GitHub Actions completes on both supported Python versions.
- [ ] Publish current CI artifacts rather than relying solely on archived evidence.
- [ ] Decide and document the project license.

## Research integrity

- [ ] Continue strengthening point-in-time and data-provenance checks.
- [ ] Extend tests for malformed, duplicated, stale, and inconsistent market data.
- [ ] Document model assumptions and limitations next to every research metric.
- [ ] Keep synthetic demo data clearly labelled and reproducible.

## Engineering quality

- [ ] Maintain English-language user-facing documentation and CLI diagnostics.
- [ ] Keep install/build workflows reproducible and dependencies minimal.
- [ ] Review dependency and workflow action pinning during release preparation.

No roadmap item authorizes live trading or live order submission.
