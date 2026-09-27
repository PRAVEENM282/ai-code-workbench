from contextvars import ContextVar

correlation_context: ContextVar[str] = ContextVar("correlation_id", default="-")
