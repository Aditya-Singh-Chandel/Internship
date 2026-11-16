"""Phoenix tracing: structure of the spans, redaction, labels attached to traces, and failing safe. No network needed."""
import json
import sys

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core import tracing
from app.models.user import User
from app.services import chat_service
from evals.seed import FROZEN_NOW, STAFF_ONLY_CANARY, sid


@pytest.fixture()
def spans(monkeypatch):
    """Routes spans into memory for the duration of one test and restores tracing afterwards."""
    saved = (tracing._tracer, tracing._initialised, tracing._provider)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracing.use_tracer_for_tests(provider.get_tracer("test"))
    monkeypatch.delenv("PHOENIX_REDACT_CONTENT", raising=False)
    yield exporter
    tracing._tracer, tracing._initialised, tracing._provider = saved


def by_name(exporter):
    return {s.name: s for s in exporter.get_finished_spans()}


# ---------------- basics ----------------
def test_tracing_is_a_no_op_when_off(monkeypatch):
    saved = (tracing._tracer, tracing._initialised)
    tracing._tracer, tracing._initialised = None, True
    try:
        with tracing.span("anything", "CHAIN", input="hi") as s:
            s.set("x", "y")
        assert s.span_id is None and s.trace_id is None
        assert tracing.enabled() is False
    finally:
        tracing._tracer, tracing._initialised = saved


def test_nested_spans_share_one_trace_and_carry_openinference_kinds(spans):
    with tracing.span("root", "CHAIN", input="q") as root:
        with tracing.span("search", "RETRIEVER", input="q") as child:
            child.set("retrieval.documents.0.document.content", "doc text")
    s = by_name(spans)
    assert s["search"].parent.span_id == s["root"].context.span_id
    assert s["search"].context.trace_id == s["root"].context.trace_id
    assert s["root"].attributes["openinference.span.kind"] == "CHAIN"
    assert s["search"].attributes["openinference.span.kind"] == "RETRIEVER"
    assert root.span_id == format(s["root"].context.span_id, "016x") and len(root.trace_id) == 32


def test_extra_facts_become_searchable_metadata_only_inside_the_block(spans):
    with tracing.attributes(case_id="pol-pets-mayfair", category="policy"):
        with tracing.span("inside"):
            pass
    with tracing.span("outside"):
        pass
    s = by_name(spans)
    assert json.loads(s["inside"].attributes["metadata"]) == {"case_id": "pol-pets-mayfair", "category": "policy"}
    assert "metadata" not in s["outside"].attributes


# ---------------- redaction ----------------
def test_redaction_drops_all_text_but_keeps_numbers_and_ids(spans, monkeypatch):
    monkeypatch.setenv("PHOENIX_REDACT_CONTENT", "true")
    with tracing.span("llm", "LLM", input="my secret question") as s:
        s.set("output.value", "my secret answer")
        s.set("llm.input_messages.0.message.content", "system text")
        s.set("retrieval.documents.0.document.content", "document text")
        s.set("llm.token_count.total", 123)
        s.set("session.id", "abc")
    attrs = by_name(spans)["llm"].attributes
    assert not any("secret" in str(v) or v in ("system text", "document text") for v in attrs.values())
    assert attrs["llm.token_count.total"] == 123 and attrs["session.id"] == "abc"


def test_redaction_off_keeps_text(spans):
    with tracing.span("llm", "LLM", input="hello") as s:
        s.set("output.value", "world")
    attrs = by_name(spans)["llm"].attributes
    assert attrs["input.value"] == "hello" and attrs["output.value"] == "world"


# ---------------- annotations (labels shown beside a trace) ----------------
class Recorder:
    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), []

    def __call__(self, url, params=None, json=None, timeout=None):
        self.calls.append({"url": url, "params": params, "json": json})
        return httpx.Response(self.statuses.pop(0), text="x")


def test_annotation_payload_matches_the_phoenix_api(monkeypatch):
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix.test:6006/")
    monkeypatch.delenv("PHOENIX_REDACT_CONTENT", raising=False)
    rec = Recorder([200])
    monkeypatch.setattr(tracing.httpx, "post", rec)
    assert tracing.annotate_span("abc123", "exact_checks", label="fail", score=0.0, explanation="missing 3 PM", metadata={"case_id": "x"})
    call = rec.calls[0]
    assert call["url"] == "http://phoenix.test:6006/v1/span_annotations" and call["params"] == {"sync": "true"}
    item = call["json"]["data"][0]
    assert item["span_id"] == "abc123" and item["name"] == "exact_checks" and item["annotator_kind"] == "CODE"
    assert item["result"] == {"label": "fail", "score": 0.0, "explanation": "missing 3 PM"}
    assert item["metadata"] == {"case_id": "x"}


def test_annotation_is_retried_until_the_span_is_ingested(monkeypatch):
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix.test:6006")
    monkeypatch.setattr(tracing.time, "sleep", lambda s: None)
    rec = Recorder([404, 404, 200])
    monkeypatch.setattr(tracing.httpx, "post", rec)
    assert tracing.annotate_span("abc", "n", label="pass") and len(rec.calls) == 3


def test_annotation_gives_up_quietly(monkeypatch):
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix.test:6006")
    monkeypatch.setattr(tracing.time, "sleep", lambda s: None)
    monkeypatch.setattr(tracing.httpx, "post", Recorder([500]))
    assert tracing.annotate_span("abc", "n", label="pass") is False

    def unreachable(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(tracing.httpx, "post", unreachable)
    assert tracing.annotate_span("abc", "n", label="pass") is False


def test_annotation_does_nothing_without_an_endpoint_or_span(monkeypatch):
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    rec = Recorder([200])
    monkeypatch.setattr(tracing.httpx, "post", rec)
    assert tracing.annotate_span("abc", "n", label="pass") is False
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix.test:6006")
    assert tracing.annotate_span(None, "n", label="pass") is False
    assert rec.calls == []


def test_redaction_also_strips_annotation_explanations(monkeypatch):
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix.test:6006")
    monkeypatch.setenv("PHOENIX_REDACT_CONTENT", "true")
    rec = Recorder([200])
    monkeypatch.setattr(tracing.httpx, "post", rec)
    tracing.annotate_span("abc", "n", label="fail", explanation="the answer said something private")
    assert rec.calls[0]["json"]["data"][0]["result"]["explanation"] is None


# ---------------- failing safe ----------------
def test_missing_packages_or_bad_setup_never_break_the_chatbot(monkeypatch):
    saved = (tracing._tracer, tracing._initialised, tracing._provider)
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:9")
    monkeypatch.setitem(sys.modules, "opentelemetry.exporter.otlp.proto.http.trace_exporter", None)  # import now fails
    tracing._tracer, tracing._initialised, tracing._provider = None, False, None
    try:
        with tracing.span("still works", "CHAIN") as s:
            pass
        assert s.span_id is None and tracing.enabled() is False
    finally:
        tracing._tracer, tracing._initialised, tracing._provider = saved


# ---------------- the real chat path ----------------
def test_one_question_is_one_trace_with_retrieval_and_generation(db, spans, monkeypatch):
    from app.services import llm_service

    def fake_gemini(prompt, system_instruction=None, conversation_history=None, temperature=0.3, usage=None, **kw):
        usage.update({"model": "fake-model", "prompt_tokens": 100, "output_tokens": 20, "total_tokens": 120})
        return "Yes, dogs up to 25 kg are welcome."

    monkeypatch.setattr(llm_service, "call_gemini_cloud_api", fake_gemini)
    user = db.query(User).filter(User.email == "marcus.vance@test.hms").first()
    result = chat_service.send_chat_message(db, "Are pets allowed?", user=user, hotel_id=sid("hotel:mayfair"), debug=True, now=FROZEN_NOW)

    s = by_name(spans)
    root, retrieval, llm = s["concierge_chat"], s["knowledge_retrieval"], s["gemini_generate"]
    assert retrieval.parent.span_id == llm.parent.span_id == root.context.span_id
    assert root.attributes["session.id"] == str(result["session_id"])
    assert root.attributes["user.id"] == str(user.id) and root.attributes["hms.authenticated"] is True
    assert retrieval.attributes["openinference.span.kind"] == "RETRIEVER"
    assert any(k.startswith("retrieval.documents.") and k.endswith(".document.content") for k in retrieval.attributes)
    assert llm.attributes["llm.token_count.total"] == 120 and llm.attributes["llm.model_name"] == "fake-model"
    # Phoenix renders these as a chat: system prompt, then the guest's message; and the answer
    assert llm.attributes["llm.input_messages.0.message.role"] == "system"
    assert "Are pets allowed?" in [v for k, v in llm.attributes.items() if k.endswith("message.content")]
    assert llm.attributes["llm.output_messages.0.message.content"] == "Yes, dogs up to 25 kg are welcome."
    # the ids the eval runner uses to label this trace
    assert result["debug"]["trace"] == {"trace_id": format(root.context.trace_id, "032x"), "span_id": format(root.context.span_id, "016x")}


def test_anonymous_guests_are_traced_without_identity_and_staff_secrets_never_enter_spans(db, spans, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "call_gemini_cloud_api", lambda *a, usage=None, **k: (usage.update({"model": "m"}), "ok")[1])
    chat_service.send_chat_message(db, "Tell me about the night safe", hotel_id=sid("hotel:mayfair"), now=FROZEN_NOW)
    root = by_name(spans)["concierge_chat"]
    assert root.attributes["user.id"] == "anonymous"
    everything = json.dumps({s.name: dict(s.attributes) for s in spans.get_finished_spans()}, default=str)
    assert STAFF_ONLY_CANARY not in everything       # staff_only chunks are never retrieved, so never traced
    assert "marcus.vance@test.hms" not in everything  # user emails are not put in spans
