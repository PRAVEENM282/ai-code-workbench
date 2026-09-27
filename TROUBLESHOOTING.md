# Troubleshooting

- **Frontend loads but Generate says no provider:** set a provider model identifier and matching API key in `.env`, then restart the backend. Check `GET /api/v1/providers` (it reports configured status only).
- **Provider returns 502:** inspect backend logs using the response correlation ID. Confirm the configured endpoint, model availability, key scope, outbound TLS/network, and provider quota. The API retries transient 429/5xx/timeouts with bounded backoff.
- **Static analyzer warning that a tool is unavailable:** verify the backend image was rebuilt after dependency changes and that configured commands are installed on `PATH`. Analysis returns partial results instead of failing the request.
- **Database readiness fails:** check `docker compose ps`, `docker compose logs postgres backend`, database credentials, health state, and migration output. PostgreSQL data survives `docker compose down`; deleting volumes does not.
- **Port already in use:** change the relevant `*_HOST_PORT` setting in `.env`; container-side ports remain separately configured.
- **Monaco editor blank:** inspect browser console/network for worker/CSP errors, verify frontend CSP permits `worker-src blob:`, and ensure assets were built with a supported Node runtime.
- **CI dependency scan fails:** inspect npm/pip/Trivy advisory output, upgrade the affected direct/transitive package, regenerate the lockfile, and rerun the full suite. Do not suppress high/critical findings without a time-bounded security exception.

For local API details see [API.md](API.md); for public deployment prerequisites see [SECURITY.md](SECURITY.md).
