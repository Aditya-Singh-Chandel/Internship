"""The Gemini client's tool loop, with a scripted fake Gemini (no network, no quota)."""

import httpx
import pytest
from fastapi import HTTPException

from app.services import llm_service

TOOLS = [{"functionDeclarations": [{"name": "check_availability", "description": "d", "parameters": {"type": "OBJECT", "properties": {}}}]}]


def reply(parts, prompt=10, out=5):
    return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": parts}}],
                                     "usageMetadata": {"promptTokenCount": prompt, "candidatesTokenCount": out, "totalTokenCount": prompt + out}})


def call(name="check_availability", args=None, call_id="call_1", signature="sig-1"):
    part = {"functionCall": {"name": name, "args": args or {"checkin_date": "2026-11-10"}, "id": call_id}}
    if signature:
        part["thoughtSignature"] = signature
    return part


class FakeGemini:
    """Replaces httpx.Client: records every request body and plays back scripted responses."""

    def __init__(self, script):
        self.script, self.requests = list(script), []

    def __call__(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):
        self.requests.append({"url": url, "body": json})
        return self.script.pop(0)


@pytest.fixture()
def gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    def install(script):
        fake = FakeGemini(script)
        monkeypatch.setattr(llm_service.httpx, "Client", fake)
        return fake
    return install


def ask(**kwargs):
    return llm_service.call_gemini_cloud_api("Is the Aspen Lodge free 10-12 Nov?", system_instruction="rules", **kwargs)


def test_a_question_that_needs_no_lookup_costs_exactly_one_request(gemini):
    fake = gemini([reply([{"text": "Check-in is at 4 PM."}])])
    runner_calls = []
    usage = {}
    text = ask(tools=TOOLS, tool_runner=lambda n, a: runner_calls.append(n), usage=usage)
    assert text == "Check-in is at 4 PM." and runner_calls == []
    assert len(fake.requests) == 1 and fake.requests[0]["body"]["tools"] == TOOLS
    assert usage["requests"] == 1 and usage["total_tokens"] == 15


def test_without_tools_nothing_changes_for_the_model(gemini):
    fake = gemini([reply([{"text": "hello"}])])
    assert ask() == "hello"
    assert "tools" not in fake.requests[0]["body"] and "toolConfig" not in fake.requests[0]["body"]


def test_one_tool_round_trip(gemini):
    fake = gemini([reply([call()], prompt=100, out=10), reply([{"text": "Yes, 3 rooms are free."}], prompt=150, out=20)])
    seen = []

    def runner(name, args):
        seen.append((name, args))
        return {"ok": True, "rows": [{"room_type": "Alpine Queen", "rooms_available": 3}]}

    usage = {}
    assert ask(tools=TOOLS, tool_runner=runner, usage=usage) == "Yes, 3 rooms are free."
    assert seen == [("check_availability", {"checkin_date": "2026-11-10"})]

    second = fake.requests[1]["body"]["contents"]
    assert second[-2] == {"role": "model", "parts": [call()]}                          # echoed verbatim, thoughtSignature included
    answer_part = second[-1]["parts"][0]["functionResponse"]
    assert second[-1]["role"] == "user" and answer_part["name"] == "check_availability" and answer_part["id"] == "call_1"
    assert answer_part["response"]["rows"][0]["rooms_available"] == 3
    assert usage["requests"] == 2 and usage["tool_rounds"] == 1
    assert (usage["prompt_tokens"], usage["output_tokens"], usage["total_tokens"]) == (250, 30, 280)   # added up over both requests


def test_several_calls_in_one_reply_are_all_answered_in_order(gemini):
    fake = gemini([reply([call(args={"a": 1}, call_id="c1"), call(name="check_availability", args={"a": 2}, call_id="c2", signature=None)]),
                   reply([{"text": "done"}])])
    order = []
    assert ask(tools=TOOLS, tool_runner=lambda n, a: order.append(a["a"]) or {"ok": True}) == "done"
    assert order == [1, 2]
    responses = fake.requests[1]["body"]["contents"][-1]["parts"]
    assert [r["functionResponse"]["id"] for r in responses] == ["c1", "c2"]


def test_a_model_that_keeps_asking_is_cut_off_and_must_answer(gemini):
    fake = gemini([reply([call(call_id=f"c{i}")]) for i in range(3)] + [reply([{"text": "Best I can say."}])])
    runs = []
    text = ask(tools=TOOLS, tool_runner=lambda n, a: runs.append(1) or {"ok": True}, max_tool_rounds=2)
    assert text == "Best I can say." and len(runs) == 2                                  # tool ran twice, not three times
    assert fake.requests[-1]["body"]["toolConfig"] == {"functionCallingConfig": {"mode": "NONE"}}


def test_a_crashing_tool_is_reported_to_the_model_not_raised(gemini):
    fake = gemini([reply([call()]), reply([{"text": "Sorry, I couldn't check that."}])])

    def boom(name, args):
        raise RuntimeError("database exploded")

    assert ask(tools=TOOLS, tool_runner=boom) == "Sorry, I couldn't check that."
    sent = fake.requests[1]["body"]["contents"][-1]["parts"][0]["functionResponse"]["response"]
    assert sent == {"ok": False, "error": "the lookup failed"}


def test_a_busy_model_falls_back_and_the_loop_still_completes(gemini):
    fake = gemini([httpx.Response(503, json={"error": {"message": "overloaded"}}), reply([call()]), reply([{"text": "ok"}])])
    assert ask(tools=TOOLS, tool_runner=lambda n, a: {"ok": True}) == "ok"
    assert len(fake.requests) == 3


def test_empty_replies_move_on_to_the_next_model(gemini):
    gemini([httpx.Response(200, json={"candidates": [{"content": {"parts": []}}]}), reply([{"text": "second model"}])])
    assert ask() == "second model"


def test_thought_parts_are_not_shown_to_guests(gemini):
    gemini([reply([{"text": "internal reasoning", "thought": True}, {"text": "Visible answer."}])])
    assert ask() == "Visible answer."


def test_all_models_failing_is_a_clean_503(gemini):
    gemini([httpx.Response(503, json={})] * 3)
    with pytest.raises(HTTPException) as err:
        ask()
    assert err.value.status_code == 503 and "temporarily unavailable" in err.value.detail


def test_missing_key_is_a_clean_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(HTTPException) as err:
        ask()
    assert err.value.status_code == 503


def test_the_api_key_travels_in_a_header_never_in_the_url(gemini, monkeypatch):
    seen = {}
    fake = gemini([reply([{"text": "x"}])])
    original = fake.post

    def spy(url, json=None, headers=None):
        seen.update(url=url, headers=headers)
        return original(url, json=json, headers=headers)

    fake.post = spy
    ask()
    assert "test-key" not in seen["url"] and seen["headers"]["x-goog-api-key"] == "test-key"
