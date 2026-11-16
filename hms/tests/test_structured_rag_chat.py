"""Structured RAG inside the real chat flow: prompt, tool use, what is saved, cited, traced and scoped."""
import json

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core import tracing
from app.models.chat import ChatMessage
from app.models.user import User
from app.services import chat_service, llm_service
from app.services.structured_rag_service import StructuredTools
from evals.seed import FROZEN_NOW, sid


def fake_gemini_that_uses_tools(*plan):
    """A stand-in for Gemini that behaves like the real loop: asks for each (tool, args), receives the REAL tool result,
    then answers. Returns (callable, log) where log records what the tools returned and what the prompt contained."""
    log = {"results": [], "system_instruction": None, "tools": None}

    def fake(prompt, system_instruction=None, conversation_history=None, temperature=0.3, usage=None, tools=None, tool_runner=None, **kw):
        log["system_instruction"], log["tools"] = system_instruction, tools
        for name, args in plan:
            log["results"].append(tool_runner(name, args))
        if usage is not None:
            usage.update({"model": "fake", "total_tokens": 10, "requests": 1 + bool(plan), "tool_rounds": int(bool(plan))})
        return "Here is what I found."
    return fake, log


def ask(db, monkeypatch, plan, message="Is the Skyline Suite free 3-5 Nov?", user_email=None, hotel_id=None, **kw):
    fake, log = fake_gemini_that_uses_tools(*plan)
    monkeypatch.setattr(llm_service, "call_gemini_cloud_api", fake)
    user = db.query(User).filter(User.email == user_email).first() if user_email else None
    result = chat_service.send_chat_message(db, message, user=user, hotel_id=hotel_id, debug=True, now=FROZEN_NOW, **kw)
    return result, log


AVAIL = ("check_availability", {"hotel_name": "Shibuya", "room_type_name": "Skyline Suite", "checkin_date": "2026-11-03", "checkout_date": "2026-11-05"})


def test_the_model_is_offered_the_tools_and_told_todays_date_and_the_rules(db, monkeypatch):
    _, log = ask(db, monkeypatch, [])
    names = {d["name"] for group in log["tools"] for d in group["functionDeclarations"]}
    assert names == {"search_hotels", "search_room_types", "check_availability", "catalog_stats"}
    prompt = log["system_instruction"]
    assert "TODAY'S DATE: Sunday 2026-11-01" in prompt                      # 1 Nov 2026 is a Sunday
    assert "LIVE DATA TOOLS" in prompt and "NEVER state availability" in prompt
    assert "Do NOT call a tool for policies" in prompt


def test_tool_results_come_from_the_real_database_and_are_saved_cited_and_exposed_in_debug(db, monkeypatch):
    result, log = ask(db, monkeypatch, [AVAIL])
    assert log["results"][0]["rows"][0]["rooms_available"] == 0              # Sophia holds the only Skyline Suite

    debug_call = result["debug"]["tool_calls"][0]
    assert debug_call["name"] == "check_availability" and debug_call["ok"] and debug_call["result"]["rows"][0]["room_type"] == "Skyline Suite"

    saved = db.query(ChatMessage).filter(ChatMessage.id == result["message_id"]).one()
    assert saved.tool_calls_json["calls"][0]["name"] == "check_availability"
    assert "result" not in saved.tool_calls_json["calls"][0]                  # results are not stored in the history table
    assert any(c["source_type"] == "database" and "check_availability" in c["title"] for c in result["citations"])
    assert result["debug"]["llm"]["tool_rounds"] == 1


def test_a_failed_lookup_is_reported_to_the_model_and_cited_nowhere(db, monkeypatch):
    bad = ("check_availability", {"checkin_date": "2026-10-01", "checkout_date": "2026-10-03"})   # in the past
    result, log = ask(db, monkeypatch, [bad])
    assert log["results"][0]["ok"] is False and "in the past" in log["results"][0]["error"]
    assert not any(c["source_type"] == "database" for c in result["citations"])
    assert result["debug"]["tool_calls"][0]["ok"] is False


def test_a_chat_without_lookups_records_no_tool_calls(db, monkeypatch):
    result, _ = ask(db, monkeypatch, [], message="What is the check-in time?")
    saved = db.query(ChatMessage).filter(ChatMessage.id == result["message_id"]).one()
    assert saved.tool_calls_json == {"calls": []} and result["debug"]["tool_calls"] == []


def test_a_chat_scoped_to_one_hotel_cannot_look_at_the_others(db, monkeypatch):
    plan = [("search_hotels", {}), ("check_availability", {"checkin_date": "2026-11-10", "checkout_date": "2026-11-12"})]
    _, log = ask(db, monkeypatch, plan, hotel_id=sid("hotel:aspen"))
    assert [r["hotel"] for r in log["results"][0]["rows"]] == ["GrandStay Aspen Lodge"]
    assert {r["hotel"] for r in log["results"][1]["rows"]} == {"GrandStay Aspen Lodge"}


def test_the_guests_own_data_never_appears_in_tool_results(db, monkeypatch):
    plan = [("search_hotels", {}), ("catalog_stats", {"metric": "avg_rating", "group_by": "hotel"}), AVAIL]
    _, log = ask(db, monkeypatch, plan, user_email="marcus.vance@test.hms")
    text = json.dumps(log["results"])
    assert "marcus" not in text.lower() and "@" not in text


def test_a_crashing_lookup_does_not_lose_the_guests_message(db, monkeypatch):
    def broken(self, args):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(StructuredTools, "_check_availability", broken)
    monkeypatch.setitem(StructuredTools.__init__.__globals__, "_unused", None)
    fake, log = fake_gemini_that_uses_tools()
    # the handler table was built in __init__ from bound methods, so patch through a fresh tool object instead
    original_init = StructuredTools.__init__

    def init(self, *a, **k):
        original_init(self, *a, **k)
        self._handlers["check_availability"] = lambda args: broken(self, args)

    monkeypatch.setattr(StructuredTools, "__init__", init)
    result, log = ask(db, monkeypatch, [AVAIL])
    assert log["results"][0]["ok"] is False
    contents = [(m.role, m.content) for m in db.query(ChatMessage).filter(ChatMessage.session_id == result["session_id"]).order_by(ChatMessage.created_at)]
    assert [role for role, _ in contents] == ["user", "assistant"]            # the guest's message survived the failed lookup


# ---------------- Phoenix sees each lookup as a child step ----------------
@pytest.fixture()
def spans():
    saved = (tracing._tracer, tracing._initialised, tracing._provider)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracing.use_tracer_for_tests(provider.get_tracer("test"))
    yield exporter
    tracing._tracer, tracing._initialised, tracing._provider = saved


def test_each_lookup_is_a_tool_span_inside_the_generation_span(db, monkeypatch, spans):
    ask(db, monkeypatch, [AVAIL])
    by_name = {s.name: s for s in spans.get_finished_spans()}
    tool, llm = by_name["tool_check_availability"], by_name["gemini_generate"]
    assert tool.parent.span_id == llm.context.span_id
    assert tool.attributes["tool.name"] == "check_availability" and tool.attributes["hms.rows"] == 1
    assert json.loads(tool.attributes["tool.parameters"])["room_type_name"] == "Skyline Suite"
    assert llm.attributes["hms.tool_calls"] == 1
