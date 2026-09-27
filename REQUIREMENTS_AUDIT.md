# Requirements Audit

## Objective and acceptance boundary

Build a containerized, single-workspace AI coding workbench. Users edit source in Monaco, request code generation or code review, see real static-analysis findings beside model feedback, and retrieve persisted request history. The supplied specification is the acceptance baseline; this audit records ambiguities and implementation decisions needed to make it testable.

## Functional requirements

- React, TypeScript, Vite, and Monaco editor with Python and JavaScript modes at minimum; selecting a language updates Monaco immediately.
- Prompt, language, and task controls; distinct Generate and Analyze actions; loading, empty, error, retry, success, offline, and skeleton states.
- Render static-analysis results as Monaco markers/decorations and hover messages as well as in the results pane.
- FastAPI endpoints: `POST /api/v1/generate`, `POST /api/v1/analyze`, `GET /api/v1/history`, `GET /api/v1/health`, `GET /api/v1/metrics`, `GET /api/v1/providers`, and `GET /api/v1/version`.
- Generation returns raw code, optional explanation, and the routed model. Analysis returns normalized deterministic findings, structured AI feedback, and the routed model. History is newest first.
- Persist requests, audit records, system events, prompt templates, model configurations, feature flags, analysis runs, provider metrics, and errors with UUID identifiers and appropriate relationships/indexes.
- Use versioned external prompt templates for generation, review, security, refactor, translation, testing, and documentation; support selecting versions and rolling back active configuration.
- Route using weighted task, token, complexity, language, latency, provider-health, and cost signals. Keep routing policies replaceable and expose controlled A/B and canary selection.
- Implement OpenAI, Anthropic, Groq, and Gemini adapters. Support Ollama, OpenRouter, and Together through configurable OpenAI-compatible endpoints without adding routing logic.
- Run Pylint, Flake8, and Bandit for Python; ESLint for JavaScript; ESLint and TypeScript compiler checks for TypeScript. Normalize outputs to a common schema.
- Start frontend, backend, and PostgreSQL with one Compose command. Initialize schema automatically and wait for database health before API startup.
- Provide deployment documentation/configuration for Compose, ECS, Kubernetes, Railway, Render, and Fly.io.

## Non-functional requirements

- Clean Architecture boundaries: `domain`, `application`, `infrastructure`, `presentation`, and `shared`; keep route handlers thin.
- Async database and provider I/O; bounded concurrency, request size limits, subprocess timeouts, and bounded retries with exponential backoff for transient provider failures.
- Stable JSON API contracts, OpenAPI documentation, predictable error envelopes, and version metadata.
- Externalize mutable settings, provider/model identifiers, service URLs, port values, prompts, feature flags, and UI copy. Fixed API paths remain contract identifiers.
- Support horizontal scaling of stateless frontend/API containers; PostgreSQL is the durable state store.
- Coverage target of at least 80%, plus lint, type checks, tests, builds, and security scans in CI.

## Security requirements

- Provider credentials stay in backend environment/secret configuration and never reach browser bundles or logs.
- Validate request schemas, language/task allowlists, prompt/code sizes, and response shapes. Treat source and prompt content as untrusted data; constrain prompt injection influence.
- Do not execute submitted programs. Use fixed analyzer commands, isolated permission-restricted temporary directories, timeouts/resource bounds, sanitized environment, and guaranteed cleanup.
- Prevent shell injection by passing argument arrays; avoid user-controlled paths, analyzer flags, config loading, or plugin loading.
- Configure CSP and other browser security headers, secure cookie defaults if cookies are introduced, CSRF protections for cookie-authenticated writes, and XSS-safe rendering.
- Rate-limit API calls and guard outbound provider URLs against SSRF. Provider endpoints are operator configuration, not user input.
- Use SQLAlchemy parameterized queries, least-privilege database credentials, and avoid storing secrets in request history.

## Scalability requirements

- Stateless API processes with Postgres-backed persistence; bounded DB pools and request concurrency.
- Provider selection supports health/cost/latency feedback, configurable weights, deterministic experiment assignment, and limited canary exposure.
- Analyzer subprocess concurrency is bounded separately from API request concurrency.
- History pagination must be cursor- or page-based and indexed by creation time and UUID; unbounded history reads are disallowed.
- Provider metrics and system events need retention/aggregation controls so telemetry tables do not grow without bound.
- Aggregate raw provider observations into hourly and daily buckets before raw-row retention expires.
- Bound serialized response sizes and configure a compression threshold for large history payloads.
- Keep synchronous V1 request execution behind a replaceable workflow-dispatch boundary so durable workers can be added later.

## Deployment requirements

- Root `docker-compose.yml`, `.env.example`, backend and frontend Dockerfiles, PostgreSQL health check, API readiness check, and automatic migrations.
- Non-root containers where supported, immutable image build inputs, graceful shutdown, and configuration from environment or mounted config files.
- Keep application code cloud-neutral; deployment-specific manifests and environment mappings live outside core/domain layers.
- Missing provider credentials must not prevent services from starting; provider-dependent actions return a structured upstream-unavailable response.

## Observability requirements

- Structured logs include request correlation ID, endpoint, duration, and outcome; redact credentials and sensitive prompt/code fields by default.
- OpenTelemetry traces span HTTP request, routing, provider call, analyzer process, and persistence.
- Expose health/readiness, application/API metrics, provider latency/error metrics, analyzer duration/failure metrics, and system events.
- Record provider/model and routing decision metadata needed to explain a route without logging full user content.

## Testing requirements

- Backend unit tests for validation, routing scores, prompt selection, provider error mapping, schema behavior, and analyzer parsers.
- Integration tests with PostgreSQL for migrations, persistence, pagination, and transaction behavior.
- Router tests proving more than one model is selectable from request signals; provider-mock tests for success, timeout, rate limit, malformed output, and server failures.
- Static-analysis tests exercise real installed binaries and normalize clean/error output for supported languages.
- Frontend component/accessibility tests cover language synchronization, action states, result rendering, retry, offline, and keyboard navigation; E2E covers generate/analyze workflows.
- Coverage target 80%; CI gates lint, tests, build, and security scans.
- CI scans dependencies and container images for vulnerabilities and generates a retained SBOM for release artifacts.

## Missing contracts and decisions

| Topic | Decision for implementation | Reason |
|---|---|---|
| Authentication/ownership | One shared workspace, no user accounts or authentication | Confirmed by user; no identity/session requirements were supplied. |
| Provider credentials | Optional at startup; return structured 503 when an action has no eligible configured provider | Allows Compose health checks and UI to work before credentials are supplied. |
| Analyze task type | Optional request field defaulting to `review`; retain the required minimal contract | Enables security/refactor review prompts without breaking the specified request shape. |
| Partial analysis failure | Preserve successful side; mark the failed side with a typed error in an extended response field and emit an error event | Parallel work should not erase useful results. Provider failure still maps to the required upstream HTTP error when no AI result exists. |
| Invalid model output | Validate structured feedback; retry parsing once only when configured, then return a typed provider-output error | Prevents arbitrary text from violating API response contracts. |
| Unsupported language | Reject with 422 and an explicit supported-language list | Never report an unsupported language as having no findings. |
| Request and subprocess limits | All limits are settings, with conservative documented defaults | Avoids unbounded cost, memory, CPU, or temporary disk use. |
| History size | Paginate, newest first, with a configurable maximum page size | Required for stable latency and bounded response sizes. |
| Response storage | Enforce configurable input/output/rehydration maxima; rely on PostgreSQL TOAST below threshold and compress oversized JSON into a referenced payload blob | Controls large history rows while preserving the API response contract. |
| Response caching | Disabled by default | Outputs are nondeterministic and prompts/source may be sensitive. |
| Prompt ownership | Git templates are canonical; mounted runtime overrides supersede database activation; emergency rollback manifest has highest precedence; database stores immutable active snapshots and audit | Defines an explicit, recoverable source-of-truth hierarchy. |
| Queue | V1 runs inline behind a workflow-dispatch interface; queue and worker are future optional adapters | Provider latency does not require premature queue infrastructure, while the application boundary remains replaceable. |
| Provider metrics | Short-retention raw events roll into hourly and daily aggregates with idempotent UTC buckets | Prevents per-request telemetry from growing indefinitely. |
| UI text | Keep user-facing strings in frontend locale/config resources | Meets the externalized-copy requirement without making UI labels runtime-generated. |
| Fixed API paths | Define them once as contract routes; externalize origin/base URLs | Endpoint paths are explicit API contracts, not deployment URLs. |

## Failure scenarios to cover

- Database unavailable at startup or during writes; migration failure; pool exhaustion.
- Missing, unhealthy, rate-limited, timed-out, malformed, or overloaded provider.
- Analyzer binary missing, timeout, oversized output, invalid JSON, or unsupported language.
- Temporary-file creation/cleanup failure and unexpected subprocess exit status.
- Invalid request, oversized input, malformed history cursor, and unsupported task/language.
- Frontend offline, API timeout, partial analysis result, stale response after a newer editor action, and retry after transient errors.
- Telemetry exporter unavailable; telemetry must not take down the request path.
- Compression/decompression limits, corrupt compressed payload, and response exceeding configured maximum.
- Aggregation retry, duplicate bucket execution, and raw-row expiry before aggregation watermark.
- Queue adapter unavailable after asynchronous mode is introduced; accepted jobs must not be lost.
- Provider endpoint misconfiguration or DNS resolving to a private/metadata address.

## Explicit exclusions

- Running generated or submitted code.
- User accounts, organization tenancy, billing, remote repository access, or collaboration features.
- Persisting source code in telemetry or logs; history persistence remains part of the product contract.
