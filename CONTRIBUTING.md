# Contributing to Nodara

Thank you for helping make visual agent workflows easier to create, understand, and run.

## Before you start

- Search existing issues and pull requests before creating a duplicate.
- Use a bug report for reproducible defects and a feature request for new behavior.
- Discuss large architectural changes before investing in an implementation.
- Never include API keys, private prompts, customer data, or generated run data in an issue or commit.

## Development setup

Follow the [README quick start](README.md#quick-start), then verify both projects:

```bash
cd backend
source .venv/bin/activate
pytest -q

cd ../mobile
npm run lint
```

## Branches and commits

Create a focused branch from the current default branch:

```bash
git switch -c fix/short-description
```

Use short, imperative commit subjects. Examples:

```text
Fix parallel branch result merging
Add Anthropic-compatible model discovery
Document NewsAPI node configuration
```

Keep unrelated formatting or refactors out of a functional change.

## Architecture conventions

### LangChain creation agents

Each single request/response agent uses a three-part structure:

```text
backend/libs/langchain/
├── chains/agents/<agent_name>.py
├── prompts/agents/<agent_name>.py
└── response_models/agents/<agent_name>.py
```

- Prompts define behavior and constraints.
- Response models define structured output.
- Chains connect the prompt, provider, and response model.
- The main creation chain owns orchestration and shared state.

Tool-calling loops belong in a dedicated executor rather than a single-chain module.

### Workflow runtime

- Keep workflow creation separate from workflow execution.
- Add compiler behavior in `backend/libs/langgraph/`.
- Add concrete node behavior in `backend/libs/runtime/`.
- Preserve deterministic graph topology. Do not silently serialize parallel branches.
- Define loop limits, step limits, and failure behavior explicitly.

### Mobile

- Keep network behavior in `mobile/services/`.
- Keep shared domain contracts in `mobile/types/`.
- Use native controls and accessible names for interactive elements.
- Handle loading, empty, error, disabled, and long-content states.
- Test on a narrow phone layout before submitting visual changes.

## Testing expectations

Add or update tests for behavior changes.

Backend changes should cover:

- Successful behavior.
- Invalid input and expected errors.
- Persistence when relevant.
- Parallel, recursive, or branching edge cases when relevant.

Mobile changes must pass the TypeScript check. Include before-and-after screenshots or a short recording for visible changes.

Tests that call paid or external services must be explicitly marked and excluded from the default suite.

## Pull requests

A pull request should:

1. Explain the user problem and the chosen behavior.
2. Stay small enough to review confidently.
3. Include tests or explain why no automated test is practical.
4. Document new environment variables in `.env.example` and the README.
5. Avoid generated files, local databases, logs, and credentials.
6. Pass all automated checks.

Maintainers may request changes for correctness, security, accessibility, scope, or consistency. Review is collaborative; address the reasoning, not only the individual comment.

## Reporting security issues

Do not open a public issue for a vulnerability or credential leak. Follow [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the repository's [MIT License](LICENSE).
