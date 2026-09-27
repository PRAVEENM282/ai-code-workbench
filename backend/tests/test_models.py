from sqlalchemy import Uuid

from workbench.infrastructure.database.models import Base


def test_all_persisted_records_use_uuid_primary_keys() -> None:
    required_tables = {
        "request_history",
        "audit_log",
        "system_event",
        "prompt_template",
        "model_configuration",
        "feature_flag",
        "analysis_run",
        "provider_metrics",
        "provider_metrics_hourly",
        "provider_metrics_daily",
        "error_log",
        "migration_history",
        "response_payload_blob",
    }

    assert required_tables <= set(Base.metadata.tables)
    for table in Base.metadata.tables.values():
        assert table.primary_key.columns.keys() == ["id"]
        assert isinstance(table.primary_key.columns["id"].type, Uuid)
        assert table.primary_key.columns["id"].default.is_callable


def test_request_history_can_store_validated_open_language_labels() -> None:
    assert Base.metadata.tables["request_history"].columns["language"].type.length == 64
