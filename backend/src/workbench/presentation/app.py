import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware

from workbench.application.errors import UpstreamProviderError
from workbench.application.service import WorkbenchService
from workbench.infrastructure.analysis import StaticAnalyzer
from workbench.infrastructure.database.models import PromptTemplate
from workbench.infrastructure.database.session import make_session_factory
from workbench.infrastructure.prompts import PromptManager
from workbench.infrastructure.providers import HttpLLMProvider
from workbench.infrastructure.settings import Settings
from workbench.presentation.schemas import AnalyzeRequest, GenerateRequest
from workbench.presentation.logging_config import (
    configure_logging,
    correlation_context,
)

logger = logging.getLogger("workbench")


class RequestGuards(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int, max_requests: int, window: int) -> None:
        super().__init__(app)
        self.max_bytes, self.max_requests, self.window = max_bytes, max_requests, window
        self.calls: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        correlation = request.headers.get("x-correlation-id", str(uuid4()))[:128]
        context_token = correlation_context.set(correlation)
        if int(request.headers.get("content-length", "0") or 0) > self.max_bytes:
            response = JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "request_too_large",
                        "message": "Request exceeds configured size limit",
                    }
                },
            )
            self._security_headers(response, correlation)
            correlation_context.reset(context_token)
            return response
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        calls = [
            value for value in self.calls.get(client, []) if now - value < self.window
        ]
        if len(calls) >= self.max_requests:
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {"code": "rate_limited", "message": "Rate limit exceeded"}
                },
            )
            self._security_headers(response, correlation)
            correlation_context.reset(context_token)
            return response
        calls.append(now)
        self.calls[client] = calls
        request.state.correlation_id = correlation
        started = time.monotonic()
        try:
            response = await call_next(request)
            self._security_headers(response, correlation)
            logger.info(
                "request completed method=%s path=%s status=%s duration_ms=%d",
                request.method,
                request.url.path,
                response.status_code,
                int((time.monotonic() - started) * 1000),
            )
            return response
        finally:
            correlation_context.reset(context_token)

    @staticmethod
    def _security_headers(response, correlation: str) -> None:
        response.headers["X-Correlation-ID"] = correlation
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    runtime_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        import asyncio

        engine = create_async_engine(
            runtime_settings.database.url,
            pool_size=runtime_settings.database.pool_size,
            max_overflow=runtime_settings.database.max_overflow,
            connect_args={"timeout": runtime_settings.database.connect_timeout_seconds},
        )
        sessions = make_session_factory(runtime_settings.database, engine)
        providers = {
            name: HttpLLMProvider(
                name,
                config,
                runtime_settings.limits.provider_timeout_seconds,
                runtime_settings.limits.provider_max_retries,
            )
            for name, config in runtime_settings.providers.items()
            if config.enabled
        }
        prompts_root = Path(runtime_settings.prompts_directory)
        prompt_manager = PromptManager(
            prompts_root,
            Path(runtime_settings.prompt_overrides_directory) / "overrides",
            Path(runtime_settings.prompt_overrides_directory) / "rollback.yaml",
        )
        async with sessions() as session:
            rows = (await session.scalars(select(PromptTemplate))).all()
        prompt_manager.load_database_templates(
            [
                {
                    "name": row.name,
                    "version": row.version,
                    "system": row.body,
                    "digest": row.content_digest,
                    "source": row.source,
                    "active": str(row.active).lower(),
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                }
                for row in rows
            ]
        )
        analyzer = StaticAnalyzer(
            runtime_settings.analyzers.model_dump(),
            runtime_settings.analyzers.temporary_root,
            runtime_settings.limits.analyzer_timeout_seconds,
            runtime_settings.limits.analyzer_output_bytes,
            runtime_settings.limits.analyzer_concurrency,
            Path(runtime_settings.config_directory),
        )
        app.state.engine = engine
        app.state.service = WorkbenchService(
            runtime_settings, sessions, providers, prompt_manager, analyzer
        )
        app.state.started = time.monotonic()
        from workbench.infrastructure.metrics_rollup import roll_up_provider_metrics

        async def maintain_metrics() -> None:
            while True:
                try:
                    await roll_up_provider_metrics(sessions)
                except Exception:
                    logger.exception("provider metric rollup failed")
                await asyncio.sleep(
                    runtime_settings.limits.metrics_rollup_interval_seconds
                )

        maintenance_task = asyncio.create_task(
            maintain_metrics(), name="provider-metrics-rollup"
        )
        yield
        maintenance_task.cancel()
        await asyncio.gather(maintenance_task, return_exceptions=True)
        analyzer.close()
        await asyncio_gather_close(providers)
        await engine.dispose()

    app = FastAPI(
        title="AI Code Workbench",
        version=runtime_settings.service.version,
        lifespan=lifespan,
    )
    app.add_middleware(
        RequestGuards,
        max_bytes=runtime_settings.limits.request_bytes,
        max_requests=runtime_settings.limits.rate_limit_requests,
        window=runtime_settings.limits.rate_limit_window_seconds,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.service.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
        allow_credentials=False,
    )
    from workbench.presentation.telemetry import configure_telemetry

    configure_telemetry(app, runtime_settings.telemetry_endpoint, "ai-code-workbench")

    @app.exception_handler(UpstreamProviderError)
    async def provider_error(request: Request, error: UpstreamProviderError):
        logger.warning(
            "upstream provider failure correlation_id=%s",
            getattr(request.state, "correlation_id", ""),
        )
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "upstream_provider_failure", "message": str(error)}
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        detail = error.detail
        body = (
            detail
            if isinstance(detail, dict) and "code" in detail
            else {"code": "http_error", "message": str(detail)}
        )
        return JSONResponse(
            status_code=error.status_code,
            content={"error": body},
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "Request validation failed",
                    "details": error.errors(),
                }
            },
        )

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/health/ready")
    async def readiness(request: Request) -> dict[str, str]:
        try:
            async with request.app.state.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception as error:
            raise HTTPException(
                status_code=503, detail="Database unavailable"
            ) from error

    @app.get("/api/v1/version")
    async def version() -> dict[str, str]:
        return {"version": runtime_settings.service.version}

    @app.get("/api/v1/providers")
    async def providers(request: Request):
        return request.app.state.service.available_providers()

    @app.get("/api/v1/metrics", response_class=PlainTextResponse)
    async def metrics(request: Request):
        uptime = max(0, time.monotonic() - request.app.state.started)
        return (
            "# TYPE workbench_uptime_seconds gauge\n"
            f"workbench_uptime_seconds {uptime:.3f}\n"
        )

    @app.post("/api/v1/generate")
    async def generate(payload: GenerateRequest, request: Request):
        try:
            return await request.app.state.service.generate(payload)
        except LookupError as error:
            raise HTTPException(
                status_code=503,
                detail={"code": "no_provider_available", "message": str(error)},
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=413,
                detail={"code": "response_too_large", "message": str(error)},
            ) from error

    @app.post("/api/v1/analyze")
    async def analyze(payload: AnalyzeRequest, request: Request):
        try:
            return await request.app.state.service.analyze(payload)
        except LookupError as error:
            raise HTTPException(
                status_code=503,
                detail={"code": "no_provider_available", "message": str(error)},
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=413,
                detail={"code": "response_too_large", "message": str(error)},
            ) from error

    @app.get("/api/v1/history")
    async def history(
        request: Request,
        limit: int = Query(
            default=runtime_settings.limits.history_page_size,
            ge=1,
            le=runtime_settings.limits.history_max_page_size,
        ),
    ):
        return await request.app.state.service.history(limit)

    return app


async def asyncio_gather_close(providers: dict[str, HttpLLMProvider]) -> None:
    import asyncio

    await asyncio.gather(
        *(provider.close() for provider in providers.values()), return_exceptions=True
    )
