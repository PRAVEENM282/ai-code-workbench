import asyncio

import httpx
import pytest

from workbench.application.errors import UpstreamProviderError

from workbench.infrastructure.providers import (
    HttpLLMProvider,
    parse_feedback,
    strip_markdown_fence,
)
from workbench.infrastructure.settings import ProviderSettings


def provider(name: str = "openai") -> HttpLLMProvider:
    return HttpLLMProvider(
        name,
        ProviderSettings(
            base_url="https://provider.example/v1",
            allowed_hosts=["provider.example"],
            model="test-model",
            api_key="secret",
            cost_per_million_tokens=1,
            quality_score=0.8,
            average_latency_ms=1000,
            supported_languages=["python"],
            supported_tasks=["review"],
        ),
        timeout=1,
        retries=1,
    )


def test_provider_shapes_and_parses_response(monkeypatch) -> None:
    async def no_sleep(_):
        return None

    monkeypatch.setattr("workbench.infrastructure.providers.asyncio.sleep", no_sleep)
    instance = provider()
    calls = 0

    async def post(url, *, json, headers):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", url)
        if calls == 1:
            return httpx.Response(429, request=request)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}, request=request
        )

    monkeypatch.setattr(instance.client, "post", post)
    assert asyncio.run(instance.complete("system", "prompt")) == "ok"
    assert calls == 2
    url, body, headers = instance._request("system", "prompt", True)
    assert url.endswith("/chat/completions")
    assert body["response_format"]["type"] == "json_object"
    assert headers["Authorization"] == "Bearer secret"
    asyncio.run(instance.close())


def test_provider_specific_endpoints_and_fence_parsing() -> None:
    anthropic = provider("anthropic")
    gemini = provider("gemini")
    assert anthropic._request("s", "p", False)[0].endswith("/messages")
    assert gemini._request("s", "p", False)[0].endswith(":generateContent?key=secret")
    assert strip_markdown_fence("```python\nx = 1\n```") == "x = 1"
    assert (
        parse_feedback(
            '{"issues":[{"issue_type":"bug","description":"bad",'
            '"suggested_fix":"fix"}]}'
        )[0]["issue_type"]
        == "bug"
    )
    assert parse_feedback("not json")[0]["description"] == "not json"


def test_feedback_normalizes_markdown_wrapped_json_and_malformed_text() -> None:
    markdown = (
        '```json\n{"issues":[{"issue_type":"bug",'
        '"description":"bad","suggested_fix":"fix","line_number":3}]}\n```'
    )

    assert parse_feedback(markdown) == [
        {
            "issue_type": "bug",
            "description": "bad",
            "suggested_fix": "fix",
            "line_number": 3,
        }
    ]
    assert parse_feedback("plain provider response")[0] == {
        "issue_type": "review",
        "description": "plain provider response",
        "suggested_fix": "",
        "line_number": 1,
    }


def test_provider_retries_timeout_and_exhaustion_maps_upstream_error(
    monkeypatch,
) -> None:
    async def no_sleep(_):
        return None

    monkeypatch.setattr("workbench.infrastructure.providers.asyncio.sleep", no_sleep)
    instance = provider()
    calls = 0

    async def post(url, *, json, headers):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", url)
        if calls == 1:
            raise httpx.ReadTimeout("temporary timeout", request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "recovered"}}]},
            request=request,
        )

    monkeypatch.setattr(instance.client, "post", post)
    assert asyncio.run(instance.complete("system", "prompt")) == "recovered"
    assert calls == 2
    asyncio.run(instance.close())

    exhausted = provider()
    exhausted_calls = 0

    async def failing_post(url, *, json, headers):
        nonlocal exhausted_calls
        exhausted_calls += 1
        request = httpx.Request("POST", url)
        return httpx.Response(500, request=request)

    monkeypatch.setattr(exhausted.client, "post", failing_post)
    with pytest.raises(UpstreamProviderError, match=r"Provider request failed \(500\)"):
        asyncio.run(exhausted.complete("system", "prompt"))
    assert exhausted_calls == 2
    asyncio.run(exhausted.close())


def test_provider_rejects_private_and_non_allowlisted_endpoints() -> None:
    from pydantic import ValidationError
    import pytest

    config = ProviderSettings(
        base_url="http://127.0.0.1/v1",
        allowed_hosts=["127.0.0.1"],
        model="model",
        cost_per_million_tokens=1,
        quality_score=1,
        average_latency_ms=1,
        supported_languages=["python"],
        supported_tasks=["review"],
    )
    with pytest.raises(ValueError, match="HTTPS"):
        HttpLLMProvider("openai", config, timeout=1, retries=0)

    with pytest.raises(ValidationError):
        ProviderSettings(
            base_url="https://provider.example/v1",
            model="model",
            cost_per_million_tokens=1,
            quality_score=1,
            average_latency_ms=1,
            supported_languages=["python"],
            supported_tasks=["review"],
        )
