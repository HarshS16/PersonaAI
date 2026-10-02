"""Observability: Prometheus metrics, security headers, Sentry, OpenTelemetry.

Everything here degrades gracefully: metrics and security headers are always on,
while Sentry and OpenTelemetry activate only when their env vars are set (and,
for OTel, only when the instrumentation packages are installed).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("observability")

REQUESTS = Counter(
    "http_requests_total", "HTTP requests", ["method", "path", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)

# Secure defaults; HSTS is only meaningful over HTTPS so it's gated on production.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


def _route_template(request: Request) -> str:
    """Low-cardinality label: the matched route template, not the raw path."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class MetricsAndSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        path = _route_template(request)
        REQUESTS.labels(request.method, path, response.status_code).inc()
        LATENCY.labels(request.method, path).observe(time.perf_counter() - start)

        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def setup_sentry() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    log.info("sentry_enabled")


def setup_otel(app: object) -> None:
    """Instrument FastAPI, SQLAlchemy and httpx when an OTLP endpoint is set.

    Requires the `observability` extra (opentelemetry-*). If it isn't installed,
    this logs and returns rather than failing startup.
    """
    if not settings.otel_exporter_otlp_endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("otel_not_installed", hint="pip install '.[observability]'")
        return

    provider = TracerProvider(resource=Resource.create({"service.name": "personaai-api"}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    trace.set_tracer_provider(provider)

    from app.core.db import engine

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    HTTPXClientInstrumentor().instrument()
    log.info("otel_enabled", endpoint=settings.otel_exporter_otlp_endpoint)
