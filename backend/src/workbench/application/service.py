import asyncio
import hashlib
import gzip
import json
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from workbench.application.errors import UpstreamProviderError
from workbench.domain.routing import ProviderCandidate, RouteSignals, WeightedTaskRouter
from workbench.infrastructure.analysis import StaticAnalyzer
from workbench.infrastructure.database.models import (
    AnalysisRun,
    AuditLog,
    ErrorLog,
    ModelConfiguration,
    PromptTemplate,
    ProviderMetrics,
    RequestHistory,
    ResponsePayloadBlob,
)
from workbench.infrastructure.prompts import PromptManager
from workbench.infrastructure.providers import (
    HttpLLMProvider,
    parse_feedback,
    strip_markdown_fence,
)
from workbench.infrastructure.settings import Settings
from workbench.shared.context import correlation_context


class WorkbenchService:
    def __init__(
        self,
        settings: Settings,
        sessions: async_sessionmaker,
        providers: dict[str, HttpLLMProvider],
        prompt_manager: PromptManager,
        analyzer: StaticAnalyzer,
    ) -> None:
        self.settings, self.sessions, self.providers = settings, sessions, providers
        self.prompt_manager, self.analyzer = prompt_manager, analyzer
        candidates = [
            ProviderCandidate(
                name,
                cfg.model,
                cfg.cost_per_million_tokens,
                cfg.quality_score,
                cfg.average_latency_ms,
                frozenset(cfg.supported_languages),
                frozenset(cfg.supported_tasks),
                routing_role=cfg.routing_role,
                is_canary=cfg.canary,
                experiment_variant=cfg.experiment_variant,
            )
            for name, cfg in settings.providers.items()
            if cfg.enabled
            and cfg.model
            and (cfg.api_key.get_secret_value() or name == "ollama")
        ]
        self.router = WeightedTaskRouter(
            candidates,
            weights=settings.routing.weights,
            health={name: True for name in settings.providers},
            canary_percent=settings.routing.canary_percent,
            experiment_salt=settings.routing.experiment_salt,
            task_roles=settings.routing.task_roles,
        )
        self.provider_failures: dict[str, int] = defaultdict(int)
        self.provider_circuit_until: dict[str, float] = {}
        self.provider_slots = asyncio.Semaphore(settings.limits.provider_concurrency)

    def available_providers(self) -> list[dict[str, Any]]:
        return [
            {
                "provider": name,
                "model": config.model,
                "enabled": config.enabled
                and bool(config.model)
                and bool(config.api_key.get_secret_value() or name == "ollama"),
                "configured": bool(config.model)
                and bool(config.api_key.get_secret_value() or name == "ollama"),
                "languages": config.supported_languages,
                "tasks": config.supported_tasks,
                "routing_role": config.routing_role,
            }
            for name, config in self.settings.providers.items()
        ]

    def _route(
        self, task: str, language: str, input_text: str, target_ms: int | None = None
    ):
        tokens = max(1, len(input_text) // 4)
        complexity = min(1.0, max(0.0, (tokens / 10000) ** 0.5))
        now = time.monotonic()
        for provider in self.settings.providers:
            self.router.health[provider] = (
                self.provider_circuit_until.get(provider, 0) <= now
            )
        assignment_key = hashlib.sha256(
            f"{task}:{language}:{input_text}".encode()
        ).hexdigest()
        return self.router.route(
            RouteSignals(task, language, tokens, complexity, target_ms, assignment_key)
        )

    async def _complete(
        self, provider_name: str, system: str, prompt: str, json_mode: bool = False
    ) -> tuple[str, int]:
        started = time.monotonic()
        try:
            async with self.provider_slots:
                response = await self.providers[provider_name].complete(
                    system, prompt, json_mode=json_mode
                )
            self.provider_failures[provider_name] = 0
        except UpstreamProviderError:
            self.provider_failures[provider_name] += 1
            if (
                self.provider_failures[provider_name]
                >= self.settings.routing.failure_threshold
            ):
                self.provider_circuit_until[provider_name] = (
                    time.monotonic() + self.settings.routing.circuit_cooldown_seconds
                )
            raise
        return response, int((time.monotonic() - started) * 1000)

    async def _record(
        self,
        endpoint: str,
        task: str,
        language: str,
        user_input: str,
        routed: str,
        payload: dict[str, Any],
        latency_ms: int,
        success: bool,
        prompt: dict[str, str] | None = None,
        routing: dict[str, Any] | None = None,
    ) -> None:
        encoded = json.dumps(
            payload, separators=(",", ":"), ensure_ascii=False
        ).encode()
        if len(encoded) > self.settings.limits.response_bytes:
            raise ValueError("Response exceeds configured maximum response size")
        async with self.sessions() as session, session.begin():
            model_config = await session.scalar(
                select(ModelConfiguration).where(
                    ModelConfiguration.provider == routed.split("/", 1)[0],
                    ModelConfiguration.model == routed.split("/", 1)[-1],
                )
            )
            if model_config is None:
                model_config = ModelConfiguration(
                    provider=routed.split("/", 1)[0], model=routed.split("/", 1)[-1]
                )
                session.add(model_config)
                await session.flush()
            row = RequestHistory(
                endpoint_used=endpoint,
                task_type=task,
                language=language,
                user_input=user_input,
                input_prompt=user_input if endpoint == "generate" else None,
                input_code=user_input if endpoint == "analyze" else None,
                model_routed_to=routed,
                routing_decision={
                    "decision": routing or {},
                    "prompt": {
                        key: prompt[key]
                        for key in ("name", "version", "source", "digest")
                        if prompt and key in prompt
                    },
                },
                response_payload=payload,
                status="succeeded" if success else "failed",
                correlation_id=correlation_context.get(),
            )
            session.add(row)
            await session.flush()
            if (
                len(encoded)
                >= self.settings.limits.response_compression_threshold_bytes
            ):
                blob = ResponsePayloadBlob(
                    compressed_payload=gzip.compress(encoded),
                    compression_format="gzip",
                    uncompressed_size=len(encoded),
                )
                session.add(blob)
                await session.flush()
                row.response_payload_blob_id = blob.id
                row.response_payload = None
            session.add(
                AuditLog(
                    request_history_id=row.id,
                    event_type=f"request.{endpoint}",
                    details={
                        "task_type": task,
                        "language": language,
                        "routed_model": routed,
                    },
                )
            )
            if endpoint == "analyze":
                prompt_template_id = None
                if prompt:
                    prompt_template_id = await session.scalar(
                        select(PromptTemplate.id).where(
                            PromptTemplate.name == prompt["name"],
                            PromptTemplate.version == prompt["version"],
                            PromptTemplate.content_digest == prompt["digest"],
                        )
                    )
                session.add(
                    AnalysisRun(
                        request_history_id=row.id,
                        prompt_template_id=prompt_template_id,
                        status="succeeded" if success else "failed",
                        static_analysis_output=payload.get("static_analysis", []),
                        llm_feedback=payload.get("llm_feedback", []),
                        experiment={
                            "variant": (routing or {}).get(
                                "experiment_variant", "control"
                            )
                        },
                    )
                )
            session.add(
                ProviderMetrics(
                    model_configuration_id=model_config.id,
                    request_history_id=row.id,
                    task_type=task,
                    latency_ms=latency_ms,
                    succeeded=success,
                )
            )
            if not success:
                session.add(
                    ErrorLog(
                        request_history_id=row.id,
                        component="provider",
                        error_code="upstream_failure",
                        details={"endpoint": endpoint, "routed_model": routed},
                    )
                )

    async def generate(self, request: Any) -> dict[str, Any]:
        route = self._route(
            request.task_type,
            request.language,
            request.prompt,
            request.latency_target_ms,
        )
        prompt = self.prompt_manager.get("generation")
        user_content = (
            f"Task: {request.task_type}\nLanguage: {request.language}\n"
            f"Instruction (untrusted):\n{request.prompt}"
        )
        try:
            text, elapsed = await self._complete(
                route.provider,
                prompt["system"].replace("{{language}}", request.language),
                user_content,
            )
        except UpstreamProviderError:
            await self._record(
                "generate",
                request.task_type,
                request.language,
                request.prompt,
                f"{route.provider}/{route.model}",
                {"error": "upstream_provider_failure"},
                0,
                False,
                prompt,
                {
                    "policy_version": route.policy_version,
                    "features": route.features,
                    "preferred_role": route.preferred_role,
                    "role_fallback": route.role_fallback,
                },
            )
            raise
        code = strip_markdown_fence(text)
        payload = {
            "code": code,
            "explanation": "",
            "routed_model": f"{route.provider}/{route.model}",
        }
        await self._record(
            "generate",
            request.task_type,
            request.language,
            request.prompt,
            payload["routed_model"],
            payload,
            elapsed,
            True,
            prompt,
            {
                "policy_version": route.policy_version,
                "score": route.score,
                "features": route.features,
                "experiment_variant": route.experiment_variant,
                "preferred_role": route.preferred_role,
                "role_fallback": route.role_fallback,
            },
        )
        return payload

    async def analyze(self, request: Any) -> dict[str, Any]:
        route = self._route(
            request.task_type,
            request.language,
            request.code,
            request.latency_target_ms,
        )
        template_name = (
            "security"
            if request.task_type == "security"
            else "refactor" if request.task_type == "refactor" else "review"
        )
        prompt = self.prompt_manager.get(template_name)
        user_content = (
            f"Review task: {request.task_type}\nLanguage: {request.language}\n"
            f"Source code (untrusted data):\n{request.code}"
        )
        errors: list[str] = []
        if not self.analyzer.supports_language(request.language):
            errors.append(
                f"No static analysis tool is configured for {request.language}; "
                "AI review is still available."
            )
        ai_task = self._complete(
            route.provider,
            prompt["system"].replace("{{language}}", request.language),
            user_content,
            json_mode=True,
        )
        lint_task = self.analyzer.analyze(request.code, request.language)
        ai_result, lint_result = await asyncio.gather(
            ai_task, lint_task, return_exceptions=True
        )
        feedback: list[dict[str, Any]] = []
        elapsed = 0
        if isinstance(ai_result, BaseException):
            await self._record(
                "analyze",
                request.task_type,
                request.language,
                request.code,
                f"{route.provider}/{route.model}",
                {"error": "upstream_provider_failure"},
                0,
                False,
                prompt,
                {
                    "policy_version": route.policy_version,
                    "features": route.features,
                    "preferred_role": route.preferred_role,
                    "role_fallback": route.role_fallback,
                },
            )
            raise ai_result
        text, elapsed = ai_result
        feedback = parse_feedback(text)
        if isinstance(lint_result, BaseException):
            errors.append(f"Static analysis failed: {type(lint_result).__name__}")
            static = []
        else:
            static = lint_result
        payload = {
            "static_analysis": static,
            "llm_feedback": feedback,
            "routed_model": f"{route.provider}/{route.model}",
            "analysis_errors": errors,
        }
        await self._record(
            "analyze",
            request.task_type,
            request.language,
            request.code,
            payload["routed_model"],
            payload,
            elapsed,
            not errors,
            prompt,
            {
                "policy_version": route.policy_version,
                "score": route.score,
                "features": route.features,
                "experiment_variant": route.experiment_variant,
                "preferred_role": route.preferred_role,
                "role_fallback": route.role_fallback,
            },
        )
        return payload

    async def history(self, limit: int) -> list[dict[str, Any]]:
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(RequestHistory)
                    .where(RequestHistory.deleted_at.is_(None))
                    .order_by(
                        RequestHistory.created_at.desc(), RequestHistory.id.desc()
                    )
                    .limit(limit)
                )
            ).all()
            results = []
            for row in rows:
                payload = row.response_payload
                if payload is None and row.response_payload_blob_id:
                    blob = await session.get(
                        ResponsePayloadBlob, row.response_payload_blob_id
                    )
                    if blob:
                        if (
                            blob.uncompressed_size
                            > self.settings.limits.response_decompressed_bytes
                        ):
                            raise ValueError(
                                "Stored response exceeds configured decompression limit"
                            )
                        payload = json.loads(gzip.decompress(blob.compressed_payload))
                results.append(
                    {
                        "id": str(row.id),
                        "endpoint_used": row.endpoint_used,
                        "task_type": row.task_type,
                        "language": row.language,
                        "user_input": row.user_input,
                        "model_routed_to": row.model_routed_to,
                        "response_payload": payload,
                        "created_at": (
                            row.created_at.isoformat() if row.created_at else ""
                        ),
                    }
                )
            return results
