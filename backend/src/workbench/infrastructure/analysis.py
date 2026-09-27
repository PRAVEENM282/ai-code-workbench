import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import os

# Commands are fixed configuration-owned argv; submitted source is only a file.
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import Any


class StaticAnalyzer:
    """Runs fixed argv in a private temporary directory without a shell."""

    LANGUAGE_ALIASES = {
        "python": "python",
        "py": "python",
        "javascript": "javascript",
        "js": "javascript",
        "jsx": "javascript",
        "typescript": "typescript",
        "ts": "typescript",
        "tsx": "typescript",
    }

    def __init__(
        self,
        commands: dict[str, Any],
        root: Path,
        timeout: float,
        output_limit: int,
        concurrency: int,
        config_directory: Path,
    ) -> None:
        self.commands = commands
        self.root = root
        self.config_directory = config_directory.resolve()
        self.node_modules_directory = (
            self.config_directory.parent / "backend" / "node_modules"
        )
        if not self.node_modules_directory.exists():
            self.node_modules_directory = self.config_directory.parent / "node_modules"
        self.timeout = timeout
        self.output_limit = output_limit
        self.semaphore = asyncio.Semaphore(concurrency)
        self.executor = ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="static-analysis"
        )

    def supports_language(self, language: str) -> bool:
        analyzer_language = self.LANGUAGE_ALIASES.get(language.strip().lower())
        return bool(analyzer_language and self.commands.get(analyzer_language))

    async def analyze(self, code: str, language: str) -> list[dict[str, Any]]:
        language = self.LANGUAGE_ALIASES.get(language.strip().lower(), "")
        if not language or not self.commands.get(language):
            return []
        async with self.semaphore:
            return await self._run(code, language)

    async def _run(self, code: str, language: str) -> list[dict[str, Any]]:
        suffix = {"python": ".py", "javascript": ".js", "typescript": ".ts"}[language]
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="analysis-", dir=self.root
        ) as directory:
            os.chmod(directory, 0o700)
            path = Path(directory) / f"input{suffix}"
            path.write_text(code, encoding="utf-8")
            path.chmod(0o600)
            configured = self.commands[language]
            commands = (
                configured
                if language == "python" or language == "typescript"
                else {"eslint": configured}
            )
            normalized: list[dict[str, Any]] = []
            for tool, command in commands.items():
                argv = command + [str(path)]
                if tool == "eslint":
                    argv += [
                        "--config",
                        str(self.config_directory / "eslint.config.mjs"),
                    ]
                try:
                    process = await asyncio.get_running_loop().run_in_executor(
                        self.executor,
                        partial(
                            self._run_command,
                            argv,
                            cwd=directory,
                            env={
                                "PATH": os.environ.get("PATH", ""),
                                "HOME": directory,
                                "PYLINTHOME": str(Path(directory) / ".pylint"),
                                "XDG_CACHE_HOME": directory,
                                "WORKBENCH_NODE_MODULES_DIR": str(
                                    self.node_modules_directory
                                ),
                                "PYTHONDONTWRITEBYTECODE": "1",
                                "PYTHONIOENCODING": "utf-8",
                            },
                            timeout=self.timeout,
                        ),
                    )
                    code_value = int(process.returncode or 0)
                    output = process.stdout or process.stderr
                except (OSError, subprocess.TimeoutExpired):
                    normalized.append(
                        {
                            "line_number": 1,
                            "column": 1,
                            "message": f"{tool} unavailable or timed out",
                            "severity": "warning",
                            "tool": tool,
                            "rule": f"{tool}.unavailable",
                        }
                    )
                    continue
                stdout = output[: self.output_limit].decode("utf-8", errors="replace")
                try:
                    entries = json.loads(stdout) if stdout else []
                except json.JSONDecodeError:
                    entries = self._parse_text(stdout, tool)
                if tool == "eslint":
                    entries = [
                        dict(item, tool=tool)
                        for result in entries
                        if isinstance(result, dict)
                        for item in result.get("messages", [])
                    ]
                if tool == "bandit":
                    entries = [
                        {
                            "line": item.get("line_number"),
                            "message": item.get("issue_text"),
                            "type": item.get("issue_severity"),
                            "code": item.get("test_id"),
                            "tool": tool,
                        }
                        for item in entries.get("results", [])
                    ]
                if tool == "flake8":
                    entries = self._flake8_entries(stdout)
                normalized.extend(
                    self._normalize(item, tool)
                    for item in entries
                    if isinstance(item, dict)
                )
                if code_value not in (0, 1) and not normalized:
                    normalized.append(
                        {
                            "line_number": 1,
                            "column": 1,
                            "message": f"{tool} exited unexpectedly",
                            "severity": "warning",
                            "tool": tool,
                            "rule": f"{tool}.failure",
                        }
                    )
            return normalized

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=True)

    def _run_command(
        self,
        argv: list[str],
        *,
        cwd: str,
        env: dict[str, str],
        timeout: float,
    ) -> subprocess.CompletedProcess:
        # shell=False; argv contains no user-controlled command text.
        return subprocess.run(  # nosec B603
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            check=False,
            timeout=timeout,
        )

    @staticmethod
    def _normalize(item: dict[str, Any], tool: str) -> dict[str, Any]:
        line = item.get("line", item.get("line_number", item.get("lineNumber", 1)))
        try:
            line = int(line or 1)
        except (ValueError, TypeError):
            line = 1
        return {
            "line_number": max(1, line),
            "column": int(item.get("column", 1) or 1),
            "message": str(
                item.get("message", item.get("messageText", "Static analysis finding"))
            ),
            "severity": str(
                item.get("type", item.get("severity", item.get("category", "warning")))
            ).lower(),
            "tool": str(item.get("tool", tool)),
            "rule": str(item.get("symbol", item.get("ruleId", item.get("code", "")))),
        }

    @staticmethod
    def _parse_text(output: str, tool: str) -> list[dict[str, Any]]:
        found = []
        for line in output.splitlines():
            found.append(
                {"line": 1, "message": line[:500], "type": "warning", "tool": tool}
            )
        return found

    @staticmethod
    def _flake8_entries(output: str) -> list[dict[str, Any]]:
        results = []
        for line in output.splitlines():
            try:
                _path, row, col, message = line.split(":", 3)
                code, text = message.strip().split(" ", 1)
                results.append(
                    {
                        "line": row,
                        "column": col,
                        "message": text,
                        "code": code,
                        "tool": "flake8",
                    }
                )
            except ValueError:
                continue
        return results
