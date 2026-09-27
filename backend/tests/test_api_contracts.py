import asyncio
import time
import httpx

from workbench.presentation.app import create_app
from workbench.application.errors import UpstreamProviderError


def request(app, method: str, path: str, **kwargs):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def test_health_version_and_security_headers() -> None:
    app = create_app()
    response = request(app, "GET", "/api/v1/health")
    assert response.json() == {"status": "ok"}
    assert response.headers["x-correlation-id"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert request(app, "GET", "/api/v1/version").json()["version"]


def test_validation_errors_use_stable_envelope() -> None:
    response = request(
        create_app(), "POST", "/api/v1/generate", json={"language": "python"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_workflow_and_operational_routes(monkeypatch) -> None:
    from workbench.presentation import telemetry

    monkeypatch.setattr(telemetry, "configure_telemetry", lambda *_args: None)
    app = create_app()

    class Service:
        async def generate(self, _payload):
            return {"code": "pass", "explanation": "", "routed_model": "test/model"}

        async def analyze(self, _payload):
            return {
                "static_analysis": [],
                "llm_feedback": [],
                "routed_model": "test/model",
            }

        async def history(self, _limit):
            return [{"id": "entry"}]

        def available_providers(self):
            return [{"provider": "test", "configured": True}]

    app.state.service = Service()
    app.state.started = time.monotonic()
    generated = request(
        app,
        "POST",
        "/api/v1/generate",
        json={"prompt": "make", "language": "python", "task_type": "boilerplate"},
    )
    analyzed = request(
        app, "POST", "/api/v1/analyze", json={"code": "pass", "language": "python"}
    )
    assert generated.json()["code"] == "pass"
    assert analyzed.json()["static_analysis"] == []
    assert request(app, "GET", "/api/v1/providers").json()[0]["provider"] == "test"
    assert request(app, "GET", "/api/v1/history?limit=1").json() == [{"id": "entry"}]
    assert "workbench_uptime_seconds" in request(app, "GET", "/api/v1/metrics").text


def test_provider_failure_maps_to_structured_gateway_error(monkeypatch) -> None:
    from workbench.presentation import telemetry

    monkeypatch.setattr(telemetry, "configure_telemetry", lambda *_args: None)
    app = create_app()

    class Service:
        async def generate(self, _payload):
            raise UpstreamProviderError("provider down")

    app.state.service = Service()
    response = request(
        app,
        "POST",
        "/api/v1/generate",
        json={"prompt": "make", "language": "python", "task_type": "boilerplate"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_provider_failure"


def test_missing_eligible_provider_maps_to_structured_unavailable_error(
    monkeypatch,
) -> None:
    from workbench.presentation import telemetry

    monkeypatch.setattr(telemetry, "configure_telemetry", lambda *_args: None)
    app = create_app()

    class Service:
        async def generate(self, _payload):
            raise LookupError("No configured healthy provider supports this task")

    app.state.service = Service()
    response = request(
        app,
        "POST",
        "/api/v1/generate",
        json={"prompt": "make", "language": "python", "task_type": "boilerplate"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_provider_available"
