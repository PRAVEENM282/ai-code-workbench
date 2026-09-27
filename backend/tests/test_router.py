import pytest

from workbench.domain.routing import ProviderCandidate, RouteSignals, WeightedTaskRouter


@pytest.fixture
def candidates() -> list[ProviderCandidate]:
    return [
        ProviderCandidate(
            provider="fast",
            model="model-fast",
            cost_per_million_tokens=0.1,
            quality_score=0.6,
            average_latency_ms=500,
            supported_languages=frozenset({"python"}),
            supported_tasks=frozenset({"boilerplate", "review"}),
            routing_role="fast",
        ),
        ProviderCandidate(
            provider="reasoning",
            model="model-reasoning",
            cost_per_million_tokens=3,
            quality_score=1,
            average_latency_ms=3000,
            supported_languages=frozenset({"python", "typescript"}),
            supported_tasks=frozenset({"security", "review"}),
            routing_role="reasoning",
        ),
    ]


def test_router_uses_cost_and_capability_signals(candidates) -> None:
    router = WeightedTaskRouter(
        candidates,
        weights={
            "quality": 0.7,
            "task_affinity": 0.05,
            "cost": 0.1,
            "latency": 0.05,
            "health": 0.1,
        },
    )

    simple = router.route(RouteSignals("review", "python", 100, 0.1))
    complex_review = router.route(RouteSignals("review", "python", 8000, 0.95))

    assert simple.model == "model-fast"
    assert complex_review.model == "model-reasoning"
    assert simple.score != complex_review.score


def test_router_excludes_unhealthy_or_incompatible_candidates(candidates) -> None:
    router = WeightedTaskRouter(
        candidates,
        weights={
            "quality": 0.4,
            "task_affinity": 0.2,
            "cost": 0.2,
            "latency": 0.1,
            "health": 0.1,
        },
        health={"fast": False},
    )

    decision = router.route(RouteSignals("security", "python", 100, 0.8))

    assert decision.provider == "reasoning"
    with pytest.raises(LookupError):
        router.route(RouteSignals("review", "rust", 100, 0.5))


def test_canary_assignments_are_stable_and_respect_percentage(candidates) -> None:
    candidates.append(
        ProviderCandidate(
            provider="canary",
            model="model-next",
            cost_per_million_tokens=0.1,
            quality_score=0.7,
            average_latency_ms=400,
            supported_languages=frozenset({"python"}),
            supported_tasks=frozenset({"review"}),
            is_canary=True,
            experiment_variant="candidate",
        )
    )
    router = WeightedTaskRouter(
        candidates, weights={"quality": 1}, canary_percent=100, experiment_salt="salt"
    )
    first = router.route(
        RouteSignals("review", "python", 100, 0.2, assignment_key="stable-user")
    )
    second = router.route(
        RouteSignals("review", "python", 100, 0.2, assignment_key="stable-user")
    )
    assert first == second
    assert first.provider == "canary"
    assert first.experiment_variant == "candidate"


def test_task_role_preference_overrides_weighted_score(candidates) -> None:
    router = WeightedTaskRouter(
        candidates,
        weights={"quality": 1},
        task_roles={"boilerplate": "fast", "review": "reasoning"},
    )

    simple = router.route(RouteSignals("boilerplate", "python", 100, 0.1))
    complex_review = router.route(RouteSignals("review", "python", 8000, 0.95))

    assert (simple.provider, simple.preferred_role, simple.role_fallback) == (
        "fast",
        "fast",
        False,
    )
    assert (
        complex_review.provider,
        complex_review.preferred_role,
        complex_review.role_fallback,
    ) == ("reasoning", "reasoning", False)


def test_task_role_falls_back_when_preferred_provider_is_unavailable(
    candidates,
) -> None:
    router = WeightedTaskRouter(
        candidates,
        weights={"quality": 1},
        health={"reasoning": False},
        task_roles={"review": "reasoning"},
    )

    decision = router.route(RouteSignals("review", "python", 100, 0.2))

    assert decision.provider == "fast"
    assert decision.preferred_role == "reasoning"
    assert decision.role_fallback is True


def test_wildcard_language_capability_routes_unlisted_languages() -> None:
    candidate = ProviderCandidate(
        provider="general",
        model="general-model",
        cost_per_million_tokens=0.5,
        quality_score=0.8,
        average_latency_ms=1000,
        supported_languages=frozenset({"*"}),
        supported_tasks=frozenset({"boilerplate"}),
    )
    router = WeightedTaskRouter([candidate], weights={"quality": 1})

    decision = router.route(RouteSignals("boilerplate", "elixir", 100, 0.2))

    assert decision.model == "general-model"
