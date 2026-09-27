from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml


class PromptManager:
    """Loads versioned Git prompts, then runtime overrides, then emergency rollback."""

    def __init__(self, prompts: Path, overrides: Path, rollback_file: Path) -> None:
        self.prompts = prompts
        self.overrides = overrides
        self.rollback_file = rollback_file
        self.database_templates: list[dict[str, str]] = []

    def load_database_templates(self, templates: list[dict[str, str]]) -> None:
        for item in templates:
            expected = sha256(item.get("system", "").encode()).hexdigest()
            if item.get("digest") != expected:
                raise ValueError(
                    "Stored prompt digest mismatch: "
                    f"{item.get('name')}@{item.get('version')}"
                )
        self.database_templates = templates

    def get(self, name: str) -> dict[str, str]:
        rollback = self._yaml(self.rollback_file)
        pinned = rollback.get("rollback", {}).get(name, {})
        override = self.overrides / f"{name}.yaml"
        database = sorted(
            (item for item in self.database_templates if item.get("name") == name),
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )
        options = database
        if override.exists():
            override_data = self._yaml(override)
            normalized_override = self._normalize(override_data, "runtime_override")
            if (
                not normalized_override["version"]
                or override_data.get("content_digest") != normalized_override["digest"]
            ):
                raise ValueError(
                    "Runtime prompt override must declare its matching "
                    f"content_digest: {name}"
                )
            options.append(normalized_override)
        git_path = self.prompts / f"{name}.yaml"
        if git_path.exists():
            options.append(self._normalize(self._yaml(git_path), "git"))
        if pinned.get("version"):
            for candidate in options:
                if candidate.get("version") == str(pinned["version"]) and (
                    not pinned.get("digest")
                    or candidate.get("digest") == pinned["digest"]
                ):
                    return {**candidate, "source": "rollback"}
            raise ValueError(
                f"Prompt rollback version unavailable: {name}@{pinned['version']}"
            )
        active = next((item for item in database if item.get("active") == "true"), None)
        if active:
            return {**active, "source": "database"}
        if override.exists():
            return normalized_override
        if git_path.exists():
            return self._normalize(self._yaml(git_path), "git")
        raise ValueError(f"Prompt template not found: {name}")

    @staticmethod
    def _yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Prompt file must contain a mapping: {path.name}")
        return data

    @staticmethod
    def _normalize(data: dict[str, Any], source: str) -> dict[str, str]:
        body = str(data.get("system", ""))
        return {
            "name": str(data.get("name", "")),
            "version": str(data.get("version", "")),
            "system": body,
            "source": source,
            "digest": sha256(body.encode()).hexdigest(),
        }
