# Security policy

## Supported versions

Nodara is currently a proof of concept. Security fixes are applied to the latest code on the default branch. Older commits and forks are not supported by the maintainers.

## Report a vulnerability

Do not open a public issue for a suspected vulnerability.

Use the repository's **Security** tab to open a private vulnerability report. Include:

- The affected endpoint, screen, or component.
- Reproduction steps or a minimal proof of concept.
- Expected and observed behavior.
- Potential impact.
- Suggested mitigation, if known.

Do not include real user data or active credentials. Maintainers will acknowledge the report through the private advisory, validate its impact, coordinate a fix, and disclose it after affected users have a reasonable opportunity to update.

## Security considerations for deployments

- Set `API_AUTH_TOKEN` outside local development. An empty value leaves API routes open.
- Keep `.env` files and mobile secure-storage data out of source control and support bundles.
- Treat workflow inputs, prompts, outputs, traces, and generated reports as potentially sensitive.
- Review Langfuse retention and masking settings before enabling tracing.
- Use scoped provider credentials and rotate exposed keys immediately.
- Place internet-facing deployments behind TLS, request limits, and appropriate network controls.
- Review generated workflows before enabling schedules or external side effects.

## Scope

Security reports about the Nodara source code and its default configuration are in scope. Vulnerabilities in third-party hosted providers should be reported to those providers unless Nodara uses the provider in an unsafe way.
