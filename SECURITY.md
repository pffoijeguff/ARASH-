# Security Policy

## Scope

ARASH is documented as an offline research and paper-simulation project. The public source tree is still being prepared, so this policy does not imply that a live-execution service is available.

Security-sensitive areas include research-data handling, local database integrity, generated artifacts, report verification, dependency and build integrity, accidental credential publication, and any future change that expands network or execution capabilities.

## Reporting a vulnerability

Please do not publish passwords, API keys, tokens, personal account information, private datasets, or exploit details in a public issue.

If GitHub's private vulnerability reporting is enabled for this repository, use that channel. Otherwise, contact the repository owner through the GitHub profile and share only the minimum details necessary to establish a secure reporting channel. Do not include secret values in the initial message.

Include, where safe:

- the affected revision or artifact;
- the component and preconditions involved;
- a concise impact assessment;
- minimal reproduction steps that do not expose secrets or other people's data;
- any suggested mitigation.

## Security expectations

- Never commit real credentials or local trading-account data.
- Keep test fixtures synthetic unless use of a real dataset is explicitly authorized and reviewed.
- Treat SHA-256 fingerprints as integrity checks, not proof of source authenticity.
- Keep incomplete release checks visible rather than bypassing or deleting them.
- Any future live-execution design requires a separate security review and must not be enabled implicitly by research features.