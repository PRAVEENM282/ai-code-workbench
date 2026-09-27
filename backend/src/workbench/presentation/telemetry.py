from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_telemetry(app, endpoint: str, service_name: str) -> None:
    resource = Resource.create({"service.name": service_name})
    tracer_provider = TracerProvider(resource=resource)
    metric_readers = []
    if endpoint:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        metric_readers.append(
            PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
        )
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=metric_readers)
    )
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)
