"""
Optional tracing of the AI concierge to Arize Phoenix (or any OpenTelemetry backend).

Off by default. Configure in .env:

    PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006   # turns tracing on (inside Docker use http://phoenix:6006)
    PHOENIX_PROJECT_NAME=hms                           # which Phoenix project the traces land in
    PHOENIX_REDACT_CONTENT=true                        # keep timings/tokens/ids, drop all text (questions, answers, documents)

If the OpenTelemetry packages are missing or Phoenix is unreachable the chatbot is unaffected: exporting happens on
a background thread and every failure is logged, never raised.

Span attributes follow the OpenInference conventions, which is what lets Phoenix show retrieved documents, token counts,
chat messages and sessions properly.

    with tracing.span("retrieval", "RETRIEVER", input=query) as s:
        s.set("retrieval.documents.0.document.content", text)
        print(s.span_id)

Eval runs attach extra searchable facts to every span created inside the block:

    with tracing.attributes(case_id="pol-pets-mayfair", category="policy"):
        ...
and afterwards label the finished trace:

    tracing.flush()
    tracing.annotate_span(span_id, "exact_checks", label="pass", score=1.0)
"""
import contextvars
import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

import httpx

logger = logging.getLogger(__name__)

_tracer = None
_provider = None
_initialised = False
_extra: contextvars.ContextVar = contextvars.ContextVar("hms_trace_extra", default={})


def endpoint() -> str:
    return os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").strip().rstrip("/")


def project_name() -> str:
    return os.getenv("PHOENIX_PROJECT_NAME", "").strip() or "hms"


def redacting() -> bool:
    return os.getenv("PHOENIX_REDACT_CONTENT", "").strip().lower() in ("1", "true", "yes")


def _is_text_key(key: str) -> bool:
    """Attributes that carry user or hotel text: dropped when redaction is on."""
    return key in ("input.value", "output.value") or key.endswith(".content") or key == "metadata.text"


class _NoopSpan:
    span_id = None
    trace_id = None

    def set(self, key: str, value: Any) -> None:
        pass


class _Span:
    def __init__(self, otel_span):
        self._span = otel_span
        ctx = otel_span.get_span_context()
        self.span_id = format(ctx.span_id, "016x")
        self.trace_id = format(ctx.trace_id, "032x")

    def set(self, key: str, value: Any) -> None:
        if value is None or (redacting() and _is_text_key(key)):
            return
        self._span.set_attribute(key, value if isinstance(value, (str, bool, int, float)) else str(value))


def _init() -> None:
    global _tracer, _provider, _initialised
    _initialised = True
    if not endpoint():
        return
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        _provider = TracerProvider(resource=Resource.create({
            "service.name": "hms-concierge", "openinference.project.name": project_name()}))
        _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint() + "/v1/traces", timeout=5)))
        _tracer = _provider.get_tracer("hms.concierge")
        logger.info("Tracing enabled: project %r -> %s%s", project_name(), endpoint(), " (content redacted)" if redacting() else "")
    except Exception as exc:  # missing packages or a bad endpoint must never break the chatbot
        logger.warning("Tracing requested but could not start (%s); continuing without it.", exc)


def use_tracer_for_tests(tracer) -> None:
    """Lets tests inject an in-memory tracer instead of exporting to a real backend."""
    global _tracer, _initialised
    _tracer, _initialised = tracer, True


def enabled() -> bool:
    if not _initialised:
        _init()
    return _tracer is not None


@contextmanager
def untraced() -> Iterator[None]:
    """Nothing inside this block is traced (used by /health, which Docker calls every 30 s; its SQL is just noise)."""
    try:
        from opentelemetry.instrumentation.utils import suppress_instrumentation
    except Exception:  # tracing packages not installed: there is nothing to suppress
        yield
        return
    with suppress_instrumentation():
        yield


def instrument_app(app, engine) -> None:
    """
    Whole-app tracing, on top of the concierge spans: one span per HTTP request (method, route, status, latency) and a
    child span for every SQL query it runs. A chat request therefore shows as
    POST /chat -> concierge_chat -> knowledge_retrieval / gemini_generate, with the SQL underneath.
    Health checks and static assets are skipped. Does nothing when tracing is off; a failure only logs a warning.
    """
    if not enabled() or _provider is None:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app, tracer_provider=_provider, excluded_urls="health,assets",
                                           exclude_spans=["receive", "send"])  # drop low-level ASGI message spans
        logger.info("Tracing: every HTTP request is traced")
    except Exception as exc:
        logger.warning("HTTP request tracing could not start (%s)", exc)
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=_provider)
        logger.info("Tracing: every SQL query is traced")
    except Exception as exc:
        logger.warning("SQL query tracing could not start (%s)", exc)


@contextmanager
def attributes(**facts: Any) -> Iterator[None]:
    """Facts (case id, category, run label...) attached as `metadata` to every span opened inside the block."""
    token = _extra.set({**_extra.get(), **facts})
    try:
        yield
    finally:
        _extra.reset(token)


@contextmanager
def span(name: str, kind: str = "CHAIN", input: Any = None) -> Iterator[Any]:
    """Opens a span of OpenInference `kind` (CHAIN, RETRIEVER, LLM, ...); a harmless no-op when tracing is off."""
    if not enabled():
        yield _NoopSpan()
        return
    with _tracer.start_as_current_span(name) as otel_span:
        wrapped = _Span(otel_span)
        wrapped.set("openinference.span.kind", kind)
        wrapped.set("input.value", input)
        facts = _extra.get()
        if facts:
            wrapped.set("metadata", json.dumps(facts, default=str))
        yield wrapped


def flush(timeout_seconds: float = 10.0) -> None:
    """Sends everything pending to the backend now (batches normally go out every few seconds)."""
    if _provider is not None:
        try:
            _provider.force_flush(int(timeout_seconds * 1000))
        except Exception as exc:
            logger.warning("Tracing flush failed: %s", exc)


def annotate_span(span_id: Optional[str], name: str, label: Optional[str] = None, score: Optional[float] = None,
                  explanation: Optional[str] = None, kind: str = "CODE", metadata: Optional[Dict[str, Any]] = None,
                  attempts: int = 4) -> bool:
    """
    Attaches an evaluation result (shown beside the trace in Phoenix) to a finished span. Returns True on success.
    Phoenix ingests spans a moment after they are sent, so a "not found" is retried briefly.
    """
    if not span_id or not endpoint():
        return False
    if redacting():
        explanation = None
    body = {"data": [{"span_id": span_id, "name": name, "annotator_kind": kind, "metadata": metadata or {},
                      "result": {"label": label, "score": score, "explanation": (explanation or "")[:1000] or None}}]}
    for attempt in range(1, attempts + 1):
        try:
            resp = httpx.post(endpoint() + "/v1/span_annotations", params={"sync": "true"}, json=body, timeout=15)
            if resp.status_code < 300:
                return True
            if resp.status_code not in (404, 409, 422):
                logger.warning("Phoenix rejected annotation %s: HTTP %s %s", name, resp.status_code, resp.text[:120])
                return False
        except httpx.HTTPError as exc:
            logger.warning("Could not reach Phoenix to annotate %s: %s", name, exc)
            return False
        time.sleep(attempt)  # the span may not have been ingested yet
    return False
