# API

All endpoints use the `/api/v1` prefix. FastAPI publishes its generated OpenAPI document at `/openapi.json` in development. JSON errors use `{ "error": { "code": "...", "message": "..." } }`; `X-Correlation-ID` is returned for tracing. Inputs are size-limited and validated. Provider failures return 502; unavailable routing returns 503; validation errors return 422.

`language` is an open label (1–64 characters, trimmed, starting with a letter or digit and then limited to letters, digits, spaces, `. _ + # / -`). It is not an enum, so provider prompts can target languages outside the installed tooling. Monaco uses its native language mode when registered and otherwise displays plaintext. Static analysis currently supports only configured tools; unsupported languages return an empty `static_analysis` array and an explanatory `analysis_errors` entry while AI review proceeds.

## `POST /generate`

```json
{ "prompt": "Create a dataclass for a book", "language": "python", "task_type": "boilerplate" }
```

Returns `{ "code": "...", "explanation": "", "routed_model": "provider/model" }`. Markdown fences are removed from generated code.

## `POST /analyze`

```json
{ "code": "def add(a, b): return a + b", "language": "python", "task_type": "review" }
```

Returns `static_analysis` findings with `line_number`, `column`, `message`, severity, tool, and rule; `llm_feedback` items with issue type, description, suggested fix, and line; `routed_model`; and `analysis_errors` for partial deterministic-tool failures. The linter and review run concurrently. No submitted source is executed.

## `GET /history?limit=25`

Returns persisted request records newest first. `limit` is bounded by settings. Large response payloads are gzip-compressed in a separate blob and transparently rehydrated for history reads.

## Operational endpoints

- `GET /health`: process liveness.
- `GET /health/ready`: PostgreSQL readiness.
- `GET /metrics`: lightweight Prometheus text (uptime); detailed traces/metrics export through the configured OTLP endpoint.
- `GET /providers`: configured provider/model status; secrets are never returned.
- `GET /version`: configured application version.
