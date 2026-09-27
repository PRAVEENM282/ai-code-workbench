import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from pydantic import SecretStr

from workbench.application.errors import UpstreamProviderError
from workbench.application.service import WorkbenchService
from workbench.infrastructure.database.models import (
    AnalysisRun,
    RequestHistory,
    ResponsePayloadBlob,
)
from workbench.infrastructure.settings import Settings
from workbench.presentation.schemas import AnalyzeRequest, GenerateRequest


class FakeSession:
    def __init__(self):
        self.rows = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    def begin(self):
        return self

    async def scalar(self, _query):
        return None

    def add(self, row):
        self.rows.append(row)

    async def flush(self):
        for row in self.rows:
            if getattr(row, "id", None) is None:
                row.id = uuid4()
            if isinstance(row, RequestHistory) and row.created_at is None:
                row.created_at = datetime.now(UTC)

    async def scalars(self, _query):
        return SimpleNamespace(all=lambda: [])

    async def get(self, _model, _id):
        return next(
            (row for row in self.rows if isinstance(row, ResponsePayloadBlob)), None
        )


class FakePrompts:
    def get(self, name):
        return {
            "name": name,
            "version": "1",
            "digest": "digest",
            "source": "git",
            "system": "Return code for {{language}}",
        }


class FakeAnalyzer:
    def supports_language(self, language):
        return language in {"python", "javascript", "typescript"}

    async def analyze(self, code, language):
        if not self.supports_language(language):
            return []
        return [{"line_number": 1, "message": "deterministic", "severity": "warning"}]


def make_service(tmp_path: Path):
    settings = Settings()
    providers = dict(settings.providers)
    providers["openai"] = providers["openai"].model_copy(
        update={"model": "model-a", "api_key": SecretStr("test-key")}
    )
    settings = settings.model_copy(update={"providers": providers})
    session = FakeSession()
    service = WorkbenchService(
        settings, lambda: session, {}, FakePrompts(), FakeAnalyzer()
    )
    return service, session


def test_generate_strips_fence_routes_and_persists_prompt_metadata(
    tmp_path: Path,
) -> None:
    service, session = make_service(tmp_path)

    async def complete(*_args, **_kwargs):
        return "```python\nprint('hello')\n```", 120

    service._complete = complete
    result = asyncio.run(
        service.generate(
            GenerateRequest(prompt="hello", language="python", task_type="boilerplate")
        )
    )

    assert result["code"] == "print('hello')"
    assert result["routed_model"] == "openai/model-a"
    history = next(row for row in session.rows if isinstance(row, RequestHistory))
    assert history.status == "succeeded"
    assert history.routing_decision["prompt"]["version"] == "1"
    assert history.routing_decision["decision"]["preferred_role"] == "fast"
    assert history.routing_decision["decision"]["role_fallback"] is True


def test_analyze_synthesizes_static_and_ai_findings(tmp_path: Path) -> None:
    service, session = make_service(tmp_path)

    async def complete(*_args, **_kwargs):
        return (
            '{"issues":[{"issue_type":"bug","description":"wrong",'
            '"suggested_fix":"fix","line_number":2}]}',
            240,
        )

    service._complete = complete
    result = asyncio.run(
        service.analyze(
            AnalyzeRequest(code="def f(): pass", language="python", task_type="review")
        )
    )

    assert result["static_analysis"][0]["message"] == "deterministic"
    assert result["llm_feedback"][0]["suggested_fix"] == "fix"
    assert any(isinstance(row, AnalysisRun) for row in session.rows)


def test_analyze_runs_provider_review_and_static_analysis_concurrently(
    tmp_path: Path,
) -> None:
    service, _session = make_service(tmp_path)
    branches_started: set[str] = set()
    both_started = asyncio.Event()

    async def wait_for_other_branch(branch: str) -> None:
        branches_started.add(branch)
        if len(branches_started) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=1)

    class ConcurrentAnalyzer:
        def supports_language(self, _language):
            return True

        async def analyze(self, _code, _language):
            await wait_for_other_branch("analyzer")
            return []

    async def complete(*_args, **_kwargs):
        await wait_for_other_branch("provider")
        return '{"issues":[]}', 10

    service.analyzer = ConcurrentAnalyzer()
    service._complete = complete

    response = asyncio.run(
        service.analyze(
            AnalyzeRequest(code="pass", language="python", task_type="review")
        )
    )

    assert branches_started == {"analyzer", "provider"}
    assert response["static_analysis"] == []
    assert response["llm_feedback"] == []


def test_analyze_keeps_ai_review_when_static_analysis_is_unsupported(
    tmp_path: Path,
) -> None:
    service, _session = make_service(tmp_path)

    async def complete(*_args, **_kwargs):
        return (
            '{"issues":[{"issue_type":"design","description":"Consider a guard."}]}',
            10,
        )

    service._complete = complete
    result = asyncio.run(
        service.analyze(
            AnalyzeRequest(code="fn main() {}", language="Rust", task_type="review")
        )
    )

    assert result["static_analysis"] == []
    assert result["llm_feedback"][0]["issue_type"] == "design"
    assert any(
        "Rust" in error and "static analysis" in error
        for error in result["analysis_errors"]
    )


def test_analyze_records_upstream_failure_before_reraising(tmp_path: Path) -> None:
    service, session = make_service(tmp_path)

    async def fail(*_args, **_kwargs):
        raise UpstreamProviderError("offline")

    service._complete = fail
    try:
        asyncio.run(
            service.analyze(
                AnalyzeRequest(code="pass", language="python", task_type="review")
            )
        )
    except UpstreamProviderError:
        pass
    else:
        raise AssertionError("provider failure must propagate")
    history = next(row for row in session.rows if isinstance(row, RequestHistory))
    assert history.status == "failed"
    assert history.response_payload == {"error": "upstream_provider_failure"}
