import asyncio
import os
import subprocess
from pathlib import Path

from workbench.infrastructure.analysis import StaticAnalyzer
from workbench.infrastructure.settings import Settings


def test_python_analyzer_executes_tools_and_normalizes_findings(
    tmp_path: Path, monkeypatch
) -> None:
    repository = Path(__file__).resolve().parents[2]
    monkeypatch.setenv(
        "PATH",
        f"{repository / 'backend' / 'node_modules' / '.bin'}:"
        f"{repository / 'backend' / '.venv' / 'bin'}:{os.environ['PATH']}",
    )
    analyzer = StaticAnalyzer(
        {
            "python": {
                "pylint": ["pylint", "--output-format=json", "--score=n"],
                "flake8": [
                    "flake8",
                    "--isolated",
                    "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s",
                ],
                "bandit": ["bandit", "--quiet", "--format", "json"],
            }
        },
        tmp_path,
        10,
        100_000,
        1,
        repository / "config",
    )

    findings = asyncio.run(analyzer.analyze("x=1\n", "python"))

    assert any(item["tool"] == "pylint" for item in findings)
    assert any(item["tool"] == "flake8" and item["rule"] == "E225" for item in findings)
    assert all("line_number" in item and "message" in item for item in findings)
    assert list(tmp_path.iterdir()) == []


def test_unsupported_analysis_language_returns_empty(tmp_path: Path) -> None:
    analyzer = StaticAnalyzer({}, tmp_path, 1, 100, 1, tmp_path)
    assert analyzer.supports_language("elixir") is False
    assert asyncio.run(analyzer.analyze("code", "sql")) == []
    assert list(tmp_path.iterdir()) == []


def test_analyzer_capabilities_include_only_configured_fixed_tools(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[2]
    settings = Settings()
    analyzer = StaticAnalyzer(
        settings.analyzers.model_dump(),
        tmp_path,
        settings.limits.analyzer_timeout_seconds,
        settings.limits.analyzer_output_bytes,
        1,
        repository / "config",
    )

    assert analyzer.supports_language("python") is True
    assert analyzer.supports_language("py") is True
    assert analyzer.supports_language("jsx") is True
    assert analyzer.supports_language("tsx") is True
    assert analyzer.supports_language("elixir") is False
    assert analyzer.supports_language("sql") is False


def test_timeout_is_normalized_and_temporary_directory_is_removed(
    tmp_path: Path, monkeypatch
) -> None:
    analyzer = StaticAnalyzer(
        {"python": {"pylint": ["pylint"]}}, tmp_path, 1, 100, 1, tmp_path
    )
    observed_directory = None

    def timeout(_argv, *, cwd, **_kwargs):
        nonlocal observed_directory
        observed_directory = Path(cwd)
        raise subprocess.TimeoutExpired("pylint", 1)

    monkeypatch.setattr(analyzer, "_run_command", timeout)

    findings = asyncio.run(analyzer.analyze("pass\n", "python"))

    assert findings[0]["tool"] == "pylint"
    assert "timed out" in findings[0]["message"]
    assert observed_directory is not None
    assert not observed_directory.exists()
    assert list(tmp_path.iterdir()) == []


def test_javascript_and_typescript_tools_return_normalized_results(
    tmp_path: Path, monkeypatch
) -> None:
    repository = Path(__file__).resolve().parents[2]
    monkeypatch.setenv(
        "PATH",
        f"{repository / 'backend' / 'node_modules' / '.bin'}:"
        f"{repository / 'backend' / '.venv' / 'bin'}:{os.environ['PATH']}",
    )
    settings = Settings()
    analyzer = StaticAnalyzer(
        settings.analyzers.model_dump(),
        tmp_path,
        settings.limits.analyzer_timeout_seconds,
        settings.limits.analyzer_output_bytes,
        1,
        repository / "config",
    )
    javascript = asyncio.run(analyzer.analyze("const unused = 1;\n", "javascript"))
    typescript = asyncio.run(
        analyzer.analyze('const count: number = "wrong";\n', "typescript")
    )
    assert any(item["tool"] == "eslint" for item in javascript)
    assert any(item["tool"] == "compiler" for item in typescript)
    assert all(item["line_number"] >= 1 for item in javascript + typescript)
