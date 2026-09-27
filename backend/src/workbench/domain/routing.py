from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class ProviderCandidate:
    provider: str
    model: str
    cost_per_million_tokens: float
    quality_score: float
    average_latency_ms: int
    supported_languages: frozenset[str]
    supported_tasks: frozenset[str]
    routing_role: str = "reasoning"
    is_canary: bool = False
    experiment_variant: str = "control"


@dataclass(frozen=True)
class RouteSignals:
    task_type: str
    language: str
    token_count: int
    complexity: float
    latency_target_ms: int | None = None
    assignment_key: str = ""


@dataclass(frozen=True)
class RouteDecision:
    provider: str
    model: str
    score: float
    features: dict[str, float]
    policy_version: str
    experiment_variant: str
    preferred_role: str | None = None
    role_fallback: bool = False


class WeightedTaskRouter:
    def __init__(
        self,
        candidates: list[ProviderCandidate],
        *,
        weights: dict[str, float],
        health: dict[str, bool] | None = None,
        canary_percent: float = 0,
        experiment_salt: str = "",
        policy_version: str = "weighted-v1",
        task_roles: dict[str, str] | None = None,
    ) -> None:
        self.candidates = candidates
        self.weights = weights
        self.health = health or {}
        self.canary_percent = canary_percent
        self.experiment_salt = experiment_salt
        self.policy_version = policy_version
        self.task_roles = task_roles or {}

    def route(self, signals: RouteSignals) -> RouteDecision:
        candidates = [
            candidate
            for candidate in self.candidates
            if candidate.model
            and (
                signals.language in candidate.supported_languages
                or "*" in candidate.supported_languages
            )
            and signals.task_type in candidate.supported_tasks
            and self.health.get(candidate.provider, True)
        ]
        if not candidates:
            raise LookupError(
                "No configured healthy provider supports this task and language"
            )

        preferred_role = self.task_roles.get(signals.task_type)
        preferred_candidates = [
            candidate
            for candidate in candidates
            if candidate.routing_role == preferred_role
        ]
        role_fallback = bool(preferred_role and not preferred_candidates)
        if preferred_candidates:
            candidates = preferred_candidates

        candidates = self._canary_candidates(candidates, signals.assignment_key)
        scored = [
            (self._score(candidate, signals), candidate) for candidate in candidates
        ]
        score, selected = max(
            scored, key=lambda item: (item[0][0], item[1].provider, item[1].model)
        )
        return RouteDecision(
            provider=selected.provider,
            model=selected.model,
            score=score[0],
            features=score[1],
            policy_version=self.policy_version,
            experiment_variant=selected.experiment_variant,
            preferred_role=preferred_role,
            role_fallback=role_fallback,
        )

    def _canary_candidates(
        self, candidates: list[ProviderCandidate], assignment_key: str
    ) -> list[ProviderCandidate]:
        canaries = [candidate for candidate in candidates if candidate.is_canary]
        baseline = [candidate for candidate in candidates if not candidate.is_canary]
        if not canaries or not baseline:
            return candidates
        bucket = (
            int.from_bytes(
                sha256(f"{self.experiment_salt}:{assignment_key}".encode()).digest()[
                    :4
                ],
                "big",
            )
            % 100
        )
        return canaries if bucket < self.canary_percent else baseline

    def _score(
        self, candidate: ProviderCandidate, signals: RouteSignals
    ) -> tuple[float, dict[str, float]]:
        latency_target = signals.latency_target_ms or max(
            candidate.average_latency_ms, 1
        )
        features = {
            "quality": 1 - (1 - candidate.quality_score) * signals.complexity,
            "task_affinity": 0.0 if self.task_roles.get(signals.task_type) else 1.0,
            "cost": 1 / (1 + candidate.cost_per_million_tokens),
            "latency": 1 / (1 + candidate.average_latency_ms / latency_target),
            "health": 1.0,
        }
        total_weight = sum(self.weights.get(name, 0) for name in features)
        if total_weight <= 0:
            raise ValueError("At least one routing weight must be positive")
        score = (
            sum(features[name] * self.weights.get(name, 0) for name in features)
            / total_weight
        )
        return score, features
