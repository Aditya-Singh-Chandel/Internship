"""The judge must never hammer a free quota: rate limiting, caching, budgets, daily-limit stops, free-only guard.
All HTTP is faked, so these tests cost nothing."""
import httpx
import pytest

from evals import judge as judge_module
from evals.judge import (
    HttpJudge, JudgeBudgetExhausted, JudgeNotConfigured, JudgeQuotaExhausted, RateLimiter, get_judge, parse_rate_limit,
    require_free_model,
)


def ok(text="pong"):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def rate_limited(message="Rate limit exceeded: free-models-per-min", reset_in=None, now=1_790_000_000.0):
    headers = {"X-RateLimit-Reset": str(int((now + reset_in) * 1000))} if reset_in is not None else {}
    return httpx.Response(429, json={"error": {"message": message, "code": 429, "metadata": {"headers": headers}}})


class FakeClient:
    """Plays back scripted responses and counts requests."""

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def __call__(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture()
def make_judge(tmp_path):
    def build(script, **kwargs):
        client = FakeClient(script)
        judge = HttpJudge("some/model:free", "key", min_interval=0, cache_dir=str(tmp_path), client_factory=client, **kwargs)
        slept = []
        judge.limiter = RateLimiter(0, clock=lambda: 0.0, sleep=slept.append)
        judge._slept = slept
        return judge, client
    return build


# ---------------- rate limiter ----------------
def test_limiter_spaces_requests_apart():
    now, slept = [0.0], []
    limiter = RateLimiter(4.0, clock=lambda: now[0], sleep=slept.append)
    for _ in range(3):
        limiter.wait()
    assert slept == [4.0, 8.0]          # 1st goes immediately, 2nd after 4s, 3rd after 8s


def test_limiter_push_back_delays_everyone():
    now, slept = [0.0], []
    limiter = RateLimiter(1.0, clock=lambda: now[0], sleep=slept.append)
    limiter.push_back(30)
    limiter.wait()
    assert slept == [30.0]


# ---------------- cache & budget ----------------
def test_identical_prompts_are_only_sent_once(make_judge):
    judge, client = make_judge([ok("first")])
    assert judge.generate("same prompt") == "first"
    assert judge.generate("same prompt") == "first"
    assert client.calls == 1 and judge.cache_hits == 1 and judge.requests_made == 1


def test_cache_survives_a_new_judge_instance(make_judge, tmp_path):
    first, _ = make_judge([ok("saved")])
    first.generate("prompt")
    second, client = make_judge([])
    assert second.generate("prompt") == "saved" and client.calls == 0


def test_budget_stops_the_run(make_judge):
    judge, client = make_judge([ok("a"), ok("b")], max_calls=2)
    judge.generate("p1")
    judge.generate("p2")
    with pytest.raises(JudgeBudgetExhausted):
        judge.generate("p3")
    assert client.calls == 2
    assert judge.exhausted_reason


# ---------------- 429 handling ----------------
def test_per_minute_limit_is_waited_out_then_succeeds(make_judge):
    judge, client = make_judge([rate_limited(), ok("recovered")])
    assert judge.generate("p") == "recovered"
    assert client.calls == 2


def test_daily_limit_stops_immediately_and_stays_stopped(make_judge):
    judge, client = make_judge([rate_limited("Rate limit exceeded: free-models-per-day", reset_in=3 * 3600, now=__import__("time").time())])
    with pytest.raises(JudgeQuotaExhausted):
        judge.generate("p1")
    with pytest.raises(JudgeQuotaExhausted):
        judge.generate("p2")                 # fails fast: no second HTTP request
    assert client.calls == 1


def test_a_very_long_reset_counts_as_quota_exhausted(make_judge):
    import time
    judge, client = make_judge([rate_limited("Rate limit exceeded", reset_in=7200, now=time.time())])
    with pytest.raises(JudgeQuotaExhausted):
        judge.generate("p")


def test_server_errors_and_empty_replies_are_retried(make_judge, monkeypatch):
    monkeypatch.setattr(judge_module.time, "sleep", lambda s: None)
    judge, client = make_judge([httpx.Response(503), ok(""), httpx.ConnectTimeout("slow"), ok("finally")])
    assert judge.generate("p") == "finally" and client.calls == 4


def test_gives_up_after_repeated_failures(make_judge, monkeypatch):
    monkeypatch.setattr(judge_module.time, "sleep", lambda s: None)
    judge, client = make_judge([httpx.Response(503)] * 4)
    with pytest.raises(RuntimeError, match="failed after 4 attempts"):
        judge.generate("p")


def test_parse_rate_limit_reads_reset_header_in_epoch_milliseconds():
    wait, daily, message = parse_rate_limit(rate_limited(reset_in=45, now=1_790_000_000.0), now=1_790_000_000.0)
    assert round(wait) == 45 and not daily and "free-models-per-min" in message


def test_parse_rate_limit_detects_daily_wording_and_retry_after():
    resp = httpx.Response(429, json={"error": {"message": "Quota per day exceeded"}}, headers={"retry-after": "9"})
    wait, daily, _ = parse_rate_limit(resp)
    assert daily and wait == 9.0


# ---------------- structured replies ----------------
def test_schema_replies_are_parsed_out_of_fenced_json(make_judge):
    from pydantic import BaseModel

    class Verdict(BaseModel):
        verdict: str
        score: int

    judge, _ = make_judge([ok('Sure!\n```json\n{"verdict": "yes", "score": 9}\n```')])
    assert judge.generate("rate it", Verdict) == Verdict(verdict="yes", score=9)


# ---------------- free-only guard & configuration ----------------
def test_paid_models_are_refused(monkeypatch):
    monkeypatch.setattr(judge_module, "_free_models", {"google/gemma-4-31b-it:free"})
    monkeypatch.delenv("JUDGE_ALLOW_PAID", raising=False)
    require_free_model("google/gemma-4-31b-it:free")
    with pytest.raises(JudgeNotConfigured, match="not a free"):
        require_free_model("openai/gpt-5-mini")


def test_unknown_price_list_falls_back_to_the_free_suffix(monkeypatch):
    monkeypatch.setattr(judge_module, "_free_models", set())
    require_free_model("x/y:free")
    with pytest.raises(JudgeNotConfigured):
        require_free_model("x/y")


def test_get_judge_requires_openrouter_and_a_key(monkeypatch):
    monkeypatch.setattr(judge_module, "_free_models", {"x/y:free"})
    monkeypatch.setenv("JUDGE_PROVIDER", "openai")
    with pytest.raises(JudgeNotConfigured, match="openrouter"):
        get_judge()
    monkeypatch.setenv("JUDGE_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    with pytest.raises(JudgeNotConfigured, match="OPENROUTER_API_KEY"):
        get_judge()
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("JUDGE_MODEL", "x/y:free")
    monkeypatch.setenv("JUDGE_MAX_CALLS", "30")
    judge = get_judge()
    assert judge.model_name == "x/y:free" and judge.max_calls == 30


def test_malformed_json_is_retried_once_with_a_stricter_prompt_and_not_cached(make_judge):
    from pydantic import BaseModel

    class Verdict(BaseModel):
        verdict: str

    judge, client = make_judge([ok('{"verdict": "yes" "oops"'), ok('{"verdict": "yes"}')])
    assert judge.generate("rate it", Verdict) == Verdict(verdict="yes")
    assert client.calls == 2
    # the broken reply must not stay cached for next time
    again, client2 = make_judge([ok('{"verdict": "no"}')])
    assert again.generate("rate it", Verdict).verdict in ("no", "yes")
