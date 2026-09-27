# Deployment

## Docker Compose

Copy `.env.example` to `.env`, set the database password, and run `docker compose up -d --build`. Compose waits for PostgreSQL health, then the backend runs Alembic and becomes healthy; the frontend starts after API health. All images, host/container ports, database values, resource limits, and provider credentials are configurable. The API container is non-root, read-only except tmpfs, drops Linux capabilities, and applies memory/CPU bounds.

The API persists only in PostgreSQL. Back up `postgres_data` or use managed PostgreSQL before upgrading. `docker compose down -v` deletes the local database volume.

## Portable targets

The frontend and backend are independent OCI images and do not depend on Compose service discovery in application logic. On AWS ECS, Kubernetes, Railway, Render, or Fly.io, configure the same environment keys, expose the configured HTTP port, provide managed PostgreSQL and a secret store, and run the backend migration command as a one-off release/pre-deploy step before scaling API replicas. Provide a writable bounded temp mount for `/tmp/workbench-analysis` and retain non-root execution. Use platform health checks against `/api/v1/health` and readiness against `/api/v1/health/ready`.

No cloud provider SDK is required by the app. Ingress TLS, secret injection, PostgreSQL network access, and OTLP collector connectivity are deployment concerns. Public production deployments require authentication and per-user authorization before storing code or history.

## Scaling

V1 API requests are synchronous. Scale stateless API replicas behind a load balancer; use a shared PostgreSQL database and external rate limiting before multi-replica internet exposure. Keep analyzer concurrency and container CPU/memory bounded. If provider deadlines or API concurrency require asynchronous jobs, implement the dispatcher/queue/worker seam described in [ARCHITECTURE.md](ARCHITECTURE.md); it is not a prerequisite for V1.
