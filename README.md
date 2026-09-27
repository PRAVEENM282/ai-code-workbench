# AI Code Workbench

A local-first, full-stack coding workspace that combines Monaco, weighted multi-provider LLM routing, versioned prompts, and deterministic static analysis. V1 executes requests synchronously; it does not execute user-submitted programs or cache prompts/results.

## Start locally

Prerequisites: Docker Compose v2 and a copy of `.env.example` named `.env`.

```sh
cp .env.example .env
docker compose up -d --build
```

Open the configured `FRONTEND_HOST_PORT` (default 3000). PostgreSQL health gates the API startup; the API applies Alembic migrations before serving. The UI, history, health, and analysis-tool integration start without LLM credentials. Configure at least one provider model and API key in `.env` to enable Generate and AI review. Never commit `.env`.

To stop containers while preserving database data: `docker compose down`. To remove local database data too: `docker compose down -v` (destructive).

## What it does

- Generate source code from natural-language instructions, returning raw code without Markdown fences.
- Generate and request AI review for any language label. Monaco supplies native syntax modes and language suggestions from its registry, with plaintext fallback for unknown labels. Deterministic analysis is capability-based: Python, JavaScript, and TypeScript have configured tools; other languages still receive AI review with an explicit analyzer-unavailable notice.
- Prefer configurable `fast` roles for boilerplate, tests, translation, and documentation, and `reasoning` roles for review, security, and refactoring. Among eligible providers in the preferred role, weighted scoring considers complexity/token estimate, cost, quality, latency, health, and canary assignment. If that role has no healthy configured provider, routing records and uses a safe fallback. Provider model IDs remain operator-configured.
- Analyze using fixed static-analysis commands in a permission-restricted temporary directory. Each command uses `subprocess.run` in a bounded worker thread with a timeout; source files are never executed and temporary files are cleaned up.
- Show static findings as both a results list and Monaco diagnostics/hover markers.
- Keep versioned prompts under Git, optional runtime overrides under `prompt-templates/overrides/`, and an operator rollback pin in `prompt-templates/rollback.yaml`.

## Configuration

`settings.yaml` provides non-secret defaults. Environment variables with the `WORKBENCH_` prefix override nested configuration (`WORKBENCH_PROVIDERS__GROQ__API_KEY`, for example). `.env.example` documents Compose values. Empty provider models/API keys mean “not configured”; no model identifiers or credentials are embedded in application code.

`settings.yaml` assigns provider routing roles and task preferences. Change those mappings to match the models configured for your account; provider names in the defaults do not guarantee that a particular model is available.

## Development checks

```sh
python -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[dev,analysis]'
npm ci --prefix backend
npm ci --prefix frontend
cd backend && PATH="$PWD/node_modules/.bin:$PWD/.venv/bin:$PATH" .venv/bin/pytest
cd frontend && npm run lint && npm run typecheck && npm test -- --run && npm run build
```

The pytest configuration enforces an 80% coverage floor. The browser suite uses Playwright Chromium; install it with `cd frontend && npx playwright install chromium`, then run `npm run test:e2e`.

## Documentation

- [Architecture and scaling](ARCHITECTURE.md)
- [Requirements audit](REQUIREMENTS_AUDIT.md)
- [API contract](API.md)
- [Deployment](DEPLOYMENT.md)
- [Security model](SECURITY.md)
- [Prompt operations](PROMPTS.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Contributing](CONTRIBUTING.md)
- [Final verification review](FINAL_REVIEW.md)
- [Architecture decision records](ADR/ADR-001-configurable-model-routing-and-analysis-workers.md), [open language support](ADR/ADR-002-open-language-support.md)

## V1 boundaries

Authentication/tenant isolation, a durable task queue, response caching, and user-code execution are intentionally out of scope. The current Compose deployment is a single-workspace local instance; do not expose it directly to the public internet without adding identity, authorization, TLS termination, and per-user quotas.
