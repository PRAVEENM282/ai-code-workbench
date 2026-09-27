from pathlib import Path
from typing import Literal

from pydantic import BaseModel, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from sqlalchemy import URL


class ServiceSettings(BaseModel):
    environment: str
    host: str
    port: int
    version: str
    cors_origins: list[str]


class DatabaseSettings(BaseModel):
    host: str
    port: int
    name: str
    user: str
    password: SecretStr = SecretStr("")
    pool_size: int
    max_overflow: int
    connect_timeout_seconds: float

    @property
    def url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.name,
        )


class ProviderSettings(BaseModel):
    base_url: str
    allowed_hosts: list[str]
    model: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = True
    compatible_api: bool = False
    routing_role: Literal["fast", "reasoning"] = "reasoning"
    canary: bool = False
    experiment_variant: str = "control"
    cost_per_million_tokens: float
    quality_score: float
    average_latency_ms: int
    supported_languages: list[str]
    supported_tasks: list[str]


class RoutingSettings(BaseModel):
    weights: dict[str, float]
    task_roles: dict[str, Literal["fast", "reasoning"]]
    canary_percent: float
    experiment_salt: str
    failure_threshold: int
    circuit_cooldown_seconds: int


class LimitSettings(BaseModel):
    request_bytes: int
    response_bytes: int
    response_compression_threshold_bytes: int
    response_decompressed_bytes: int
    history_page_size: int
    history_max_page_size: int
    analyzer_timeout_seconds: float
    analyzer_output_bytes: int
    analyzer_concurrency: int
    provider_timeout_seconds: float
    provider_max_retries: int
    provider_concurrency: int
    metrics_rollup_interval_seconds: int
    rate_limit_requests: int
    rate_limit_window_seconds: int


class AnalyzerSettings(BaseModel):
    python: dict[str, list[str]]
    javascript: list[str]
    typescript: dict[str, list[str]]
    temporary_root: Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKBENCH_",
        env_nested_delimiter="__",
        yaml_file="../settings.yaml",
        yaml_file_encoding="utf-8",
        extra="ignore",
    )

    service: ServiceSettings
    database: DatabaseSettings
    providers: dict[str, ProviderSettings]
    routing: RoutingSettings
    limits: LimitSettings
    analyzers: AnalyzerSettings
    config_directory: Path
    prompts_directory: Path
    prompt_overrides_directory: Path
    feature_flags_directory: Path
    telemetry_endpoint: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )
