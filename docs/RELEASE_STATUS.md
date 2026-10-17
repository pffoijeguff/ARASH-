# Release Status — 28.0.0

## Package identity

- Version: `28.0.0`
- Python requirement: `>=3.12`
- Verification evidence date: 2026-10-16
- Evidence file: `artifacts/release-gate-28.0.0.json`
- Source archive SHA-256: `4e0a677eb6a5438068609dc392f58c312066604ddde13641ed23fe627085d04b`

## Archived verification results

The provided archive records a run on CPython 3.13.5 with network access disabled and no live orders submitted: 24 checks passed, 0 failed, and 1 was incomplete because Ruff was not installed. The archive also records 301 passing pytest cases, 11/11 smoke checks, successful compilation, and successful wheel-artifact/isolated-install checks.

These results describe the supplied archive, not a freshly executed CI run from the public repository. The complete suite was not revalidated in this packaging environment; a local full-suite attempt exceeded the available execution window. Python 3.12 and hosted GitHub Actions remain unverified until CI completes. The release should therefore be considered **incomplete pending fresh CI verification**.

## Before declaring the release verified

1. Run the release gate from a clean environment on Python 3.12 and 3.13.
2. Install Ruff and resolve lint findings.
3. Confirm both GitHub Actions matrix jobs pass.
4. Review the generated reports and publish the new artifacts.
5. Resolve the project license declaration before encouraging redistribution.
