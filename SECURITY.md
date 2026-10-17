# Security Policy

## Scope and operating boundary

ARASH Foundation 28.0.0 is an offline-first research and paper-simulation project. Live order submission is out of scope. Optional market-data connectors are read-only and should be invoked only when explicitly required.

## Reporting a vulnerability

Do not publish credentials, private account data, or exploit details in a public issue. Contact the repository owner through a private channel available on the repository profile. Include the affected version, a concise impact statement, and a reproducible description that contains no personal or secret data.

## Maintainer and contributor rules

- Never commit API keys, exchange credentials, tokens, private keys, wallet secrets, `.env` files, local databases, or private datasets.
- Treat every external payload and imported file as untrusted input.
- New network adapters require explicit review of authentication, rate limits, timeouts, retries, logging, and failure behavior.
- Do not introduce live order-submission code or a mode that enables it.
- Do not log credential headers or sensitive request metadata.
- Back up local databases before changing software versions; migrations are not a substitute for an operator-managed backup.
- Content hashes and report manifests support integrity checks but do not authenticate a data provider or prove market-data correctness.
- Simulated fills, stop prices, slippage, and modeled costs are not real execution guarantees.

If a secret is accidentally committed, revoke or rotate it immediately; deleting the file in a later commit does not remove it from Git history.
