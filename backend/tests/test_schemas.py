import pytest
from pydantic import ValidationError

from workbench.presentation.schemas import AnalyzeRequest, GenerateRequest


@pytest.mark.parametrize("language", ["python", "C++", "C#", "Objective-C", "elixir"])
def test_generation_accepts_open_language_names(language: str) -> None:
    request = GenerateRequest(
        prompt="Write a function", language=f" {language} ", task_type="boilerplate"
    )

    assert request.language == language


@pytest.mark.parametrize("language", ["python", "C++", "C#", "Objective-C", "elixir"])
def test_analysis_accepts_open_language_names(language: str) -> None:
    request = AnalyzeRequest(code="source", language=f" {language} ")

    assert request.language == language


@pytest.mark.parametrize(
    "language", ["", "  ", "bad\nname", "x" * 65, "java\x00script"]
)
@pytest.mark.parametrize("request_type", [GenerateRequest, AnalyzeRequest])
def test_requests_reject_invalid_language_names(language, request_type) -> None:
    payload = {"language": language, "prompt": "Write code", "code": "source"}

    with pytest.raises(ValidationError):
        request_type(**payload)
