# Security

## Implemented controls

- Pydantic request validation, JSON size limits, in-memory IP rate limiting, correlation IDs, secure response headers, CSP at the frontend, and no credentialed CORS.
- No cookie-based authentication is used, so CSRF tokens are not applicable in the current single-workspace UI. Do not add cookie auth without CSRF defenses and `Secure`, `HttpOnly`, and `SameSite` settings.
- SQLAlchemy parameterized statements and Alembic migrations; provider keys come from environment/secret mounts and are not returned by `/providers`.
- Prompt and code are framed as untrusted data; model output is parsed and never executed.
- Static tools are launched using fixed configured argv with no shell, a private `0700` temporary directory and `0600` source file, a bounded timeout, output cap, concurrency semaphore, cleaned temporary directory, non-root API container, read-only root filesystem, dropped capabilities, and bounded container resources. Analyzer subprocesses receive a minimal environment without provider/database secrets.
- Frontend React rendering escapes text by default. CSP limits scripts, workers, and network connections to the app origin.
- CI runs Pylint, Flake8, Bandit, ESLint, TypeScript checks, npm/pip dependency auditing, Trivy filesystem scanning, and CycloneDX SBOM generation.

## Boundaries and production caveats

The application currently assumes a trusted single user/workspace and does not authenticate requests. Do not expose it to a public network as-is. Add identity, authorization, tenant-scoped history, distributed rate limits, TLS, a managed secret store, and audit retention before multi-user deployment. Provider base URLs are operator configuration, not request input; keep them trusted and allowlisted (local Ollama is an explicit operator choice). The static analyzers parse source and do not run it, but remain third-party parsers: keep their dependencies patched and execute under container resource limits.

Responses are never cached by default due to nondeterminism and source sensitivity. History retention/deletion policy must be set by the deployment owner; database backups contain submitted code and generated responses.
