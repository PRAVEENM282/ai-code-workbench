# Contributing

1. Read [REQUIREMENTS_AUDIT.md](REQUIREMENTS_AUDIT.md), [ARCHITECTURE.md](ARCHITECTURE.md), and the relevant ADR before changing boundaries.
2. Create an issue/plan for behavior changes and add or update tests first. Keep route handlers thin and prompts out of application logic.
3. Keep secrets, endpoint/model defaults, prompt content, UI copy, and limits in environment/config/resource files rather than inline code.
4. Run backend tests with the configured coverage gate, Pylint, Flake8, Bandit, frontend ESLint/typecheck/component tests/build, and Playwright E2E for browser changes.
5. Review migration compatibility, API schema changes, security impact, response size, telemetry redaction, and documentation.

Use descriptive commits and include an ADR when changing major architecture decisions. Never add customer source, API keys, generated artifacts, or `.env` files to version control.
