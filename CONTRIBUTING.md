# Contributing to ARASH Foundation

Thank you for helping improve ARASH. The primary goals are research integrity, explicit risk boundaries, reproducibility, and maintainable engineering.

## Current state

This repository currently contains the public documentation layer; source synchronization is still outstanding. Until the source package and test suite are published, contributions should focus on documentation accuracy and review. Do not invent installation steps or report test results that have not been reproduced.

## Before proposing a change

- Describe the problem, the expected behavior, and the evidence that demonstrates the issue.
- Identify affected data contracts, report schemas, database migrations, risk rules, or command-line interfaces.
- Keep synthetic research fixtures clearly labeled and deterministic.
- Separate implemented behavior from proposed behavior.

## Engineering expectations once source is synchronized

- Prefer small, focused changes with clear responsibility and actionable error handling.
- Preserve offline-by-default behavior for tests and research examples.
- Add regression coverage for each behavior change and run the relevant test group.
- Run the complete release gate before presenting a change as release-ready.
- Keep lint, compatibility, or infrastructure checks marked incomplete when they were not run.
- Do not add a live-order path, credential collection, or hidden network behavior as part of a routine feature change.

## Research integrity

Research-related changes should preserve temporal separation, dataset/configuration identity, candidate-family definitions, transaction-cost assumptions, and explicit limitations. If a test uses synthetic data, say so. A successful unit test is evidence of the behavior tested; it is not proof of strategy profitability.

## Security and sensitive files

Never commit API keys, passwords, tokens, account identifiers, personal datasets, local ledgers, private reports, or environment files. Review the final diff before pushing. Read [Security Reporting](SECURITY.md) before publishing details of a potential vulnerability.

## Pull request checklist

- [ ] The change is scoped and its motivation is explained.
- [ ] Documentation distinguishes current behavior from future intent.
- [ ] Tests and checks are reported accurately, including skipped or incomplete items.
- [ ] Generated files and local machine artifacts are excluded unless intentionally required.
- [ ] No secrets, account data, or unauthorized datasets are included.
- [ ] Any new risk behavior includes regression tests and explicit failure semantics.

## License

No license has been selected for this repository yet. Until a license is added, do not assume that public visibility grants permission to reuse or redistribute the code.