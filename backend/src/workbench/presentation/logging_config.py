import json
import logging
from datetime import UTC, datetime

from workbench.shared.context import correlation_context


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname.lower(),
                "logger": record.name,
                "message": record.getMessage(),
                "correlation_id": correlation_context.get(),
            },
            ensure_ascii=False,
        )


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
