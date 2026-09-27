from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

Language = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._+#/-]{0,63}$",
    ),
]
TaskType = Literal[
    "generation",
    "unit_test",
    "boilerplate",
    "review",
    "security",
    "refactor",
    "translation",
    "testing",
    "documentation",
]


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    language: Language
    task_type: TaskType
    latency_target_ms: int | None = Field(default=None, ge=100, le=120_000)


class AnalyzeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=1_000_000)
    language: Language
    task_type: TaskType = "review"
    latency_target_ms: int | None = Field(default=None, ge=100, le=120_000)


class GenerateResponse(BaseModel):
    code: str
    explanation: str = ""
    routed_model: str


class AnalyzeResponse(BaseModel):
    static_analysis: list[dict[str, Any]]
    llm_feedback: list[dict[str, Any]]
    routed_model: str
    analysis_errors: list[str] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    id: UUID
    endpoint_used: str
    task_type: str
    language: str
    user_input: str
    model_routed_to: str | None
    response_payload: dict[str, Any] | None
    created_at: str
