from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RequestHistory(Base):
    __tablename__ = "request_history"
    __table_args__ = (
        Index("ix_request_history_created_id", "created_at", "id"),
        Index("ix_request_history_endpoint_task", "endpoint_used", "task_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    endpoint_used: Mapped[str] = mapped_column(String(32), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    input_prompt: Mapped[str | None] = mapped_column(Text)
    input_code: Mapped[str | None] = mapped_column(Text)
    model_routed_to: Mapped[str | None] = mapped_column(String(255))
    routing_decision: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    response_payload_blob_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("response_payload_blob.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResponsePayloadBlob(Base):
    __tablename__ = "response_payload_blob"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    compressed_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    compression_format: Mapped[str] = mapped_column(String(16), nullable=False)
    uncompressed_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_created_at", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    request_history_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("request_history.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SystemEvent(Base):
    __tablename__ = "system_event"
    __table_args__ = (Index("ix_system_event_created_at", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PromptTemplate(Base):
    __tablename__ = "prompt_template"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModelConfiguration(Base):
    __tablename__ = "model_configuration"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_provider_model"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    routing_profile: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FeatureFlag(Base):
    __tablename__ = "feature_flag"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AnalysisRun(Base):
    __tablename__ = "analysis_run"
    __table_args__ = (Index("ix_analysis_run_started_at", "started_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    request_history_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("request_history.id", ondelete="CASCADE"), nullable=False
    )
    prompt_template_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("prompt_template.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    static_analysis_output: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    llm_feedback: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    experiment: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderMetrics(Base):
    __tablename__ = "provider_metrics"
    __table_args__ = (Index("ix_provider_metrics_created_at", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    model_configuration_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("model_configuration.id", ondelete="CASCADE"), nullable=False
    )
    request_history_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("request_history.id", ondelete="SET NULL")
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProviderMetricsHourly(Base):
    __tablename__ = "provider_metrics_hourly"
    __table_args__ = (
        UniqueConstraint(
            "model_configuration_id", "bucket_start", name="uq_metrics_hour_bucket"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    model_configuration_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("model_configuration.id", ondelete="CASCADE"), nullable=False
    )
    bucket_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_histogram: Mapped[dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class ProviderMetricsDaily(Base):
    __tablename__ = "provider_metrics_daily"
    __table_args__ = (
        UniqueConstraint(
            "model_configuration_id", "bucket_date", name="uq_metrics_day_bucket"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    model_configuration_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("model_configuration.id", ondelete="CASCADE"), nullable=False
    )
    bucket_date: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_histogram: Mapped[dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class ErrorLog(Base):
    __tablename__ = "error_log"
    __table_args__ = (Index("ix_error_log_created_at", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    request_history_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("request_history.id", ondelete="SET NULL")
    )
    component: Mapped[str] = mapped_column(String(48), nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MigrationHistory(Base):
    __tablename__ = "migration_history"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    revision: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
