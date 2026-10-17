# Contributing to ARASH Foundation

Thank you for helping improve ARASH. The project's priorities are research integrity, explicit risk boundaries, reproducibility, and maintainable engineering.

## Current repository state

The public repository is currently the documentation layer for the supplied 28.0.0 reference archive. The source tree and tests still need to be synchronized. Until then, contributions should focus on documentation accuracy and review.

## Engineering expectations

- Describe the problem, expected behavior, and evidence for the issue.
- Keep changes focused and errors actionable.
- Preserve offline-by-default behavior for tests and research examples.
- Add regression coverage for behavior changes once the source tree is available.
- Report tests, lint, compatibility, and infrastructure checks accurately, including unavailable checks.
- Distinguish implemented behavior from planned behavior.
- Do not add live-order submission, credential collection, or hidden network behavior as a routine feature.

## Research integrity

Preserve dataset/configuration identity, chronological evaluation, candidate-family definitions, transaction-cost assumptions, and explicit limitations. Label synthetic fixtures. A successful test is evidence only for the behavior it tests; it is not proof of strategy profitability.

## Security

Never commit API keys, passwords, tokens, account identifiers, private datasets, local ledgers, environment files, or unrelated personal information. Review the final diff before pushing. See [Security Policy](SECURITY.md).

## Pull request checklist

- [ ] The change is scoped and its motivation is explained.
- [ ] Documentation distinguishes current behavior from future intent.
- [ ] Test results include skipped or incomplete checks.
- [ ] Generated files and local machine artifacts are excluded unless required.
- [ ] No secrets, account data, or unauthorized datasets are included.
- [ ] New risk behavior has regression tests and explicit failure semantics.

## License

The reference package declares a proprietary license placeholder pending a decision by the project owner. Until an explicit license is published, do not assume public visibility grants permission to reuse or redistribute the code.
