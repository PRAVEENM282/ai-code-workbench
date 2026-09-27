from workbench.infrastructure.settings import Settings


def test_environment_values_override_yaml(monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_SERVICE__PORT", "9100")

    settings = Settings()

    assert settings.service.port == 9100
    assert settings.database.port > 0
    assert settings.providers["groq"].routing_role == "fast"
    assert settings.providers["groq"].supported_languages == ["*"]
    assert settings.providers["openai"].routing_role == "reasoning"
    assert settings.routing.task_roles["boilerplate"] == "fast"
    assert settings.routing.task_roles["security"] == "reasoning"
