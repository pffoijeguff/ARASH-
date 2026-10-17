# Release and Verification Status

## Current reference snapshot

**Reference version:** ARASH Foundation 28.0.0  
**Overall recorded release status:** `INCOMPLETE`  
**Recorded environment:** CPython 3.13.5  
**Network used during recorded checks:** No  
**Live orders submitted:** No

The 28.0.0 archive's machine-readable release gate records 24 checks passed, 0 failed, and 1 incomplete. Ruff was unavailable in the recorded environment; it must not be described as a successful lint run.

## Reported results

| Item | Recorded result | Notes |
|---|---|---|
| Automated tests | 301 passed | 10 pytest groups |
| Smoke checks | 11/11 passed | Local-only; no live orders |
| Test-module coverage audit | PASS | 41 referenced modules; no missing or unknown modules |
| Python compilation | PASS | `compileall` completed |
| Wheel integrity | PASS | Version, CLI entry point, required package files, and test-source exclusion checked |
| Isolated install/import | PASS | Report records package version 28.0.0 |
| Ruff | UNAVAILABLE | Ruff was not installed |
| Python 3.12 | UNVERIFIED | Not independently verified |
| Hosted GitHub Actions | UNVERIFIED | Not independently verified |
| Full release gate | INCOMPLETE | 24 PASS, 0 FAIL, 1 INCOMPLETE |

Source: `ARASH_RELEASE_GATE_28.0.0.json` and `ARASH_TEST_REPORT_28.0.0.fa.md` in the supplied archive, dated 2026-10-16. These are recorded archive results, not tests run against the current GitHub tree.

## Repository publication gap

The supplied 28.0.0 archive is the selected source baseline, but its source files have not yet been synchronized into this GitHub repository. The repository therefore remains documentation-only and is not currently installable or runnable from GitHub.

The archive's SHA-256 fingerprint is:

```text
4e0a677eb6a5438068609dc392f58c312066604ddde13641ed23fe627085d04b
```

A matching fingerprint is useful for byte-level integrity checks; it does not independently prove who created the archive or that its contents are correct.

## Required publication gates

1. Synchronize the reviewed source, tests, packaging metadata, scripts, examples, and configuration files from version 28.0.0.
2. Exclude build outputs, generated `*.egg-info`, local databases, logs, private datasets, caches, and credentials.
3. Keep the public-facing documentation in English and retain only relevant, reviewed project history.
4. Re-run compilation, all tests, smoke checks, packaging validation, and the release gate from a clean checkout.
5. Install Ruff and record its actual result.
6. Verify the intended Python compatibility matrix and hosted CI.
7. Publish installation instructions only after they have been tested against the synchronized tree.

## Versioning

Version 28.0.0 identifies the supplied reference archive. It does not imply that this GitHub repository already contains that source tree or that a GitHub release has been published.
