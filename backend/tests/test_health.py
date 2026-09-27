import httpx
import pytest

from workbench.presentation.app import create_app


@pytest.mark.asyncio
async def test_health_reports_live_service() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
