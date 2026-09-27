from pathlib import Path

import yaml
from hashlib import sha256

from workbench.infrastructure.prompts import PromptManager


def test_loads_baseline_version_and_digest() -> None:
    repository = Path(__file__).resolve().parents[2]
    manager = PromptManager(
        repository / "prompts",
        repository / "prompt-templates/overrides",
        repository / "prompt-templates/rollback.yaml",
    )
    prompt = manager.get("generation")
    assert prompt["version"] == "1.0.0"
    assert len(prompt["digest"]) == 64
    assert "untrusted" in prompt["system"]


def test_rollback_pins_known_version_and_rejects_unknown(tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    overrides = tmp_path / "overrides"
    prompts.mkdir()
    overrides.mkdir()
    (prompts / "review.yaml").write_text(
        yaml.safe_dump({"name": "review", "version": "1.0", "system": "baseline"})
    )
    rollback = tmp_path / "rollback.yaml"
    rollback.write_text("rollback:\n  review:\n    version: '1.0'\n")
    manager = PromptManager(prompts, overrides, rollback)
    assert manager.get("review")["system"] == "baseline"
    rollback.write_text("rollback:\n  review:\n    version: '0.9'\n")
    try:
        manager.get("review")
    except ValueError as error:
        assert "unavailable" in str(error)
    else:
        raise AssertionError("unknown rollback must be rejected")


def test_database_activation_beats_runtime_override_and_override_digest_is_checked(
    tmp_path: Path,
) -> None:
    prompts, overrides = tmp_path / "prompts", tmp_path / "overrides"
    prompts.mkdir()
    overrides.mkdir()
    (prompts / "review.yaml").write_text("name: review\nversion: '1'\nsystem: git\n")
    body = "mounted override"
    (overrides / "review.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "review",
                "version": "2",
                "system": body,
                "content_digest": sha256(body.encode()).hexdigest(),
            }
        )
    )
    manager = PromptManager(prompts, overrides, tmp_path / "missing.yaml")
    manager.load_database_templates(
        [
            {
                "name": "review",
                "version": "3",
                "system": "database",
                "digest": sha256(b"database").hexdigest(),
                "active": "true",
            }
        ]
    )
    selected = manager.get("review")
    assert selected["system"] == "database"
    assert selected["source"] == "database"

    (overrides / "review.yaml").write_text(
        "name: review\nversion: '2'\nsystem: tampered\ncontent_digest: wrong\n"
    )
    try:
        manager.get("review")
    except ValueError as error:
        assert "content_digest" in str(error)
    else:
        raise AssertionError("tampered override must fail closed")
