import asyncio
import ipaddress
import json
import secrets
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from workbench.application.errors import UpstreamProviderError
from workbench.infrastructure.settings import ProviderSettings


class LLMProvider(Protocol):
    async def complete(
        self, system: str, prompt: str, *, json_mode: bool = False
    ) -> str: ...


class HttpLLMProvider:
    """HTTP adapter that normalizes provider-specific request and response formats."""

    def __init__(
        self, name: str, config: ProviderSettings, timeout: float, retries: int
    ) -> None:
        parsed = urlparse(config.base_url)
        host = parsed.hostname or ""
        if host.lower() not in {item.lower() for item in config.allowed_hosts}:
            raise ValueError(f"Provider endpoint host is not allowlisted: {host}")
        if parsed.scheme != "https" and not (
            name == "ollama" and parsed.scheme == "http" and host == "ollama"
        ):
            raise ValueError(
                "Provider endpoints must use HTTPS (except configured Ollama)"
            )
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and (
            address.is_private or address.is_loopback or address.is_link_local
        ):
            raise ValueError("Private provider endpoint IPs are not allowed")
        self.name, self.config, self.timeout, self.retries = (
            name,
            config,
            timeout,
            retries,
        )
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)

    async def complete(
        self, system: str, prompt: str, *, json_mode: bool = False
    ) -> str:
        if not self.config.model:
            raise UpstreamProviderError(
                f"No model is configured for provider {self.name}"
            )
        for attempt in range(self.retries + 1):
            try:
                url, body, headers = self._request(system, prompt, json_mode)
                response = await self.client.post(url, json=body, headers=headers)
                if response.status_code in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                response.raise_for_status()
                return self._response_text(response.json())
            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            ) as error:
                retryable = not isinstance(
                    error, httpx.HTTPStatusError
                ) or error.response.status_code in {429, 500, 502, 503, 504}
                if retryable and attempt < self.retries:
                    jitter = secrets.randbelow(200) / 1000
                    await asyncio.sleep(min(0.5 * 2**attempt + jitter, 4))
                    continue
                status = (
                    error.response.status_code
                    if isinstance(error, httpx.HTTPStatusError)
                    else 503
                )
                raise UpstreamProviderError(
                    f"Provider request failed ({status})"
                ) from error

    def _request(
        self, system: str, prompt: str, json_mode: bool
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        base = self.config.base_url.rstrip("/")
        key = self.config.api_key.get_secret_value()
        headers = {"Content-Type": "application/json"}
        if self.name == "anthropic":
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
            return (
                f"{base}/messages",
                {
                    "model": self.config.model,
                    "max_tokens": 4096,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
                headers,
            )
        if self.name == "gemini":
            return (
                f"{base}/models/{self.config.model}:generateContent?key={key}",
                {
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                },
                headers,
            )
        headers["Authorization"] = f"Bearer {key}"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return f"{base}/chat/completions", payload, headers

    def _response_text(self, payload: dict[str, Any]) -> str:
        if self.name == "anthropic":
            return "".join(
                item.get("text", "")
                for item in payload.get("content", [])
                if item.get("type") == "text"
            )
        if self.name == "gemini":
            return "".join(
                part.get("text", "")
                for candidate in payload.get("candidates", [])
                for part in candidate.get("content", {}).get("parts", [])
            )
        return str(payload["choices"][0]["message"].get("content", ""))

    async def close(self) -> None:
        await self.client.aclose()


def strip_markdown_fence(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        first_newline = value.find("\n")
        if first_newline >= 0:
            value = value[first_newline + 1 :]
        if value.rstrip().endswith("```"):
            value = value.rstrip()[:-3]
    return value.strip()


def parse_feedback(value: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(strip_markdown_fence(value))
        issues = parsed.get("issues", []) if isinstance(parsed, dict) else parsed
        if not isinstance(issues, list):
            return []
        return [
            {
                "issue_type": str(item.get("issue_type", "review")),
                "description": str(item.get("description", "")),
                "suggested_fix": str(item.get("suggested_fix", "")),
                "line_number": int(item.get("line_number", 1) or 1),
            }
            for item in issues
            if isinstance(item, dict)
        ]
    except (ValueError, TypeError):
        return [
            {
                "issue_type": "review",
                "description": strip_markdown_fence(value)[:2000],
                "suggested_fix": "",
                "line_number": 1,
            }
        ]
