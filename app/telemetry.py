"""OpenTelemetry setup: traces, metrics and logs from this app to Elastic (or any OTLP backend).

Turned on only when OTEL_EXPORTER_OTLP_ENDPOINT is set (in .env or otel.env) and the
OpenTelemetry packages are installed. Otherwise every helper here is a harmless no-op,
so the app runs exactly as before.

    OTEL_EXPORTER_OTLP_ENDPOINT=https://<project>.ingest.<region>.elastic.cloud:443
    OTEL_EXPORTER_OTLP_HEADERS=Authorization=ApiKey <key>

What gets sent:
  traces   every HTTP request (Flask), the call to Claude (httpx), the Elasticsearch query
           (the Elasticsearch client emits its own spans), plus two named steps:
           "understand query" and "search products"
  metrics  searches by mode and understanding source, zero-result searches, search duration,
           plus this process's CPU and memory
  logs     one log line per search, linked to its trace
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

from dotenv import load_dotenv

from app import config

load_dotenv(config.ROOT / "otel.env", override=False)

log = logging.getLogger("grocery-search")
log.setLevel(logging.INFO)

_tracer = None
_searches = None
_zero = None
_duration = None
ENABLED = False


def setup(flask_app) -> None:
    """Call once, after creating the Flask app."""
    global _tracer, _searches, _zero, _duration, ENABLED
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        print("Telemetry off (no OTEL_EXPORTER_OTLP_ENDPOINT).")
        return
    try:
        from opentelemetry import metrics, trace
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        print(f"Telemetry off (OpenTelemetry packages not installed: {exc.name}).")
        return

    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "grocery-search"),
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("DEPLOY_ENV", "dev"),
    })

    # Traces: exporters read the endpoint and API-key header from the OTEL_* environment variables.
    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tp)

    # Metrics: pushed every 30 seconds.
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=30_000)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    # Logs: Python logging → OTLP, with trace and span IDs attached automatically.
    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(lp)
    log.addHandler(LoggingHandler(level=logging.INFO, logger_provider=lp))

    # Automatic instrumentation: incoming requests, outgoing HTTP (the Claude SDK uses httpx),
    # and process CPU/memory. The Elasticsearch Python client creates its own spans.
    FlaskInstrumentor().instrument_app(flask_app)
    HTTPXClientInstrumentor().instrument()
    SystemMetricsInstrumentor(config={
        "process.runtime.cpu.utilization": None,
        "process.runtime.memory": ["rss", "vms"],
    }).instrument()

    _tracer = trace.get_tracer("grocery-search")
    meter = metrics.get_meter("grocery-search")
    _searches = meter.create_counter("searches", description="Searches handled, by mode and understanding source")
    _zero = meter.create_counter("searches.zero_results", description="Searches that returned no products")
    _duration = meter.create_histogram("search.duration", unit="ms", description="Time inside Elasticsearch per search")
    ENABLED = True
    print(f"Telemetry on → {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')}")


@contextmanager
def step(name: str, **attributes):
    """A named span around one step of a search. No-op when telemetry is off."""
    if not _tracer:
        yield None
        return
    with _tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        yield span


def record_search(mode: str | None, source: str, total: int, took_ms: int, message: str) -> None:
    attrs = {"search.mode": mode or "none", "query.understanding": source}
    if ENABLED:
        _searches.add(1, attrs)
        if total == 0:
            _zero.add(1, attrs)
        _duration.record(took_ms, attrs)
    log.info("search done: %r → %d hits in %d ms (%s, %s)", message, total, took_ms, mode, source,
             extra={"search.hits": total, "search.took_ms": took_ms, **attrs})
