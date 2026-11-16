"""
The LLM that grades answers ("judge") for DeepEval metrics. FREE MODELS ONLY.

It should not be the model being graded (models rate their own writing too generously), so a different vendor
than Gemini is preferred. Configure in .env:

    JUDGE_PROVIDER=openrouter
    JUDGE_MODEL=nvidia/nemotron-3.5-super-vl:free     # must be a free model; paid ones are refused
    OPENROUTER_API_KEY=...
    JUDGE_MIN_INTERVAL=4        # optional: seconds between calls (4s = 15/min, under the 20/min free limit)
    JUDGE_MAX_CALLS=            # optional: stop after this many real HTTP requests in one run

Free tiers are small (OpenRouter: ~20 requests/min, and ~50/day until credits are bought), so everything here is
built to spend as few requests as possible and to stop cleanly instead of hammering a limit:

  * one shared rate limiter for all threads
  * an on-disk cache: an identical prompt is never sent twice, so a stopped run resumes for free the next day
  * a call budget (JUDGE_MAX_CALLS / --max-calls)
  * a 429 is waited out when it is a per-minute limit, and stops the run (JudgeQuotaExhausted) when it is a daily
    limit, with the partial results kept
"""
import hashlib
import json
import os
import re
import threading
import time
from typing import Optional, Type

import httpx
from deepeval.models import DeepEvalBaseLLM
from pydantic import BaseModel

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", ".judge_cache")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl:free"
DEFAULT_MIN_INTERVAL = 4.0
MAX_RATE_LIMIT_WAIT = 120.0  # a longer wait than this is treated as "quota gone", not "slow down"


class JudgeNotConfigured(RuntimeError):
    pass


class JudgeQuotaExhausted(RuntimeError):
    """The provider's daily (or long) limit is used up: stop, keep partial results, resume later."""


class JudgeBudgetExhausted(RuntimeError):
    """The configured call budget for this run is used up."""


class RateLimiter:
    """Thread-safe: callers wait so that at least `min_interval` seconds separate consecutive requests."""

    def __init__(self, min_interval: float, clock=time.monotonic, sleep=time.sleep):
        self.min_interval, self._clock, self._sleep = min_interval, clock, sleep
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            delay = max(0.0, self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + self.min_interval
        if delay:
            self._sleep(delay)

    def push_back(self, seconds: float) -> None:
        """After a 429: nobody may send before `seconds` have passed."""
        with self._lock:
            self._next_allowed = max(self._next_allowed, self._clock() + seconds)


def _extract_json(text: str) -> str:
    """Models often wrap JSON in prose or code fences; return the outermost {...} block."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text


def parse_rate_limit(resp: httpx.Response, now: Optional[float] = None) -> tuple:
    """Returns (seconds_to_wait, is_daily_limit, message) for a 429 response."""
    now = time.time() if now is None else now
    try:
        err = resp.json().get("error", {})
    except ValueError:
        err = {}
    message = str(err.get("message") or resp.text[:200] or "rate limited")
    raw = json.dumps(err).lower()
    daily = any(word in raw for word in ("per-day", "per day", "daily", "perday"))

    wait = None
    headers = (err.get("metadata") or {}).get("headers") or {}
    reset = headers.get("X-RateLimit-Reset") or resp.headers.get("x-ratelimit-reset")
    if reset:
        try:
            reset_seconds = float(reset) / (1000.0 if float(reset) > 1e11 else 1.0)  # epoch in ms or s
            wait = max(0.0, reset_seconds - now)
        except ValueError:
            pass
    retry_after = resp.headers.get("retry-after")
    if wait is None and retry_after:
        try:
            wait = float(retry_after)
        except ValueError:
            pass
    return (wait if wait is not None else 20.0), daily, message


_free_models: Optional[set] = None


def require_free_model(model: str) -> None:
    """Refuses anything that is not free. The OpenRouter model list is public and states the price of each model."""
    global _free_models
    if os.getenv("JUDGE_ALLOW_PAID") == "1":
        return
    if _free_models is None:
        try:
            data = httpx.get("https://openrouter.ai/api/v1/models", timeout=60).json()["data"]
            _free_models = {m["id"] for m in data
                            if float(m["pricing"].get("prompt", 1)) == 0 and float(m["pricing"].get("completion", 1)) == 0}
        except Exception:
            _free_models = set()
    # If the price list could not be fetched, fall back to the ":free" naming convention
    if model not in _free_models and not (model.endswith(":free") and not _free_models):
        raise JudgeNotConfigured(
            f"{model!r} is not a free OpenRouter model, so it is refused (free models only). "
            "Pick one ending in ':free' from https://openrouter.ai/models?q=free")


class HttpJudge(DeepEvalBaseLLM):
    def __init__(self, model: str, api_key: str, min_interval: float = DEFAULT_MIN_INTERVAL, max_calls: Optional[int] = None,
                 cache_dir: Optional[str] = CACHE_DIR, timeout: float = 120.0, client_factory=httpx.Client):
        self.provider, self.model_name, self._api_key, self._timeout = "openrouter", model, api_key, timeout
        self.limiter = RateLimiter(min_interval)
        self.max_calls, self.cache_dir, self._client_factory = max_calls, cache_dir, client_factory
        self._lock = threading.Lock()
        self.requests_made = 0      # real HTTP requests sent (counts against the provider quota)
        self.cache_hits = 0
        self.exhausted_reason: Optional[str] = None
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    # --- DeepEval interface
    def load_model(self):
        return self

    def get_model_name(self) -> str:
        return f"openrouter:{self.model_name}"

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        if schema is not None:
            prompt += "\n\nRespond with a single valid JSON object only, no commentary and no code fences."
        text = self._complete(prompt)
        if schema is None:
            return text
        try:
            return schema.model_validate_json(_extract_json(text))
        except ValueError:  # malformed JSON (free models do this now and then): forget the bad reply and ask once more, strictly
            self._forget(prompt)
            retry = prompt + ("\n\nIMPORTANT: your previous reply was not valid JSON. Reply with ONLY one valid JSON object, "
                              "and escape all quotes and line breaks inside string values.")
            return schema.model_validate_json(_extract_json(self._complete(retry)))

    async def a_generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        return self.generate(prompt, schema)

    # --- request handling
    def _cache_path(self, prompt: str) -> Optional[str]:
        if not self.cache_dir:
            return None
        digest = hashlib.sha256(f"{self.model_name}\n{prompt}".encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, digest + ".txt")

    def _forget(self, prompt: str) -> None:
        path = self._cache_path(prompt)
        if path and os.path.exists(path):
            os.remove(path)

    def _complete(self, prompt: str, attempts: int = 4) -> str:
        path = self._cache_path(prompt)
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                content = f.read()
            with self._lock:
                self.cache_hits += 1
            return content
        if self.exhausted_reason:
            raise JudgeQuotaExhausted(self.exhausted_reason)

        last_error = "no attempt made"
        for attempt in range(1, attempts + 1):
            with self._lock:
                if self.max_calls is not None and self.requests_made >= self.max_calls:
                    self.exhausted_reason = f"call budget of {self.max_calls} requests used"
                    raise JudgeBudgetExhausted(self.exhausted_reason)
                self.requests_made += 1
            self.limiter.wait()
            try:
                with self._client_factory(timeout=self._timeout) as client:
                    resp = client.post(
                        OPENROUTER_URL, headers={"Authorization": f"Bearer {self._api_key}"},
                        json={"model": self.model_name, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}"
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 429:
                wait, daily, message = parse_rate_limit(resp)
                if daily or wait > MAX_RATE_LIMIT_WAIT:
                    self.exhausted_reason = f"provider quota exhausted: {message} (resets in about {wait / 3600:.1f} h)"
                    raise JudgeQuotaExhausted(self.exhausted_reason)
                self.limiter.push_back(wait + 1)
                last_error = f"429 {message[:120]}"
                continue
            if resp.status_code in (408, 500, 502, 503, 504):
                last_error = f"HTTP {resp.status_code}"
                time.sleep(2 ** attempt)
                continue
            if resp.status_code >= 400:  # 4xx other than 429: a request problem that retrying cannot fix
                raise RuntimeError(f"judge request rejected: HTTP {resp.status_code} {resp.text[:200]}")

            content = (resp.json()["choices"][0]["message"].get("content") or "").strip()
            if not content:  # some free models occasionally return an empty message; try again
                last_error = "empty response"
                continue
            if path:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp, path)
            return content
        raise RuntimeError(f"judge request failed after {attempts} attempts: {last_error}")


def get_judge(max_calls: Optional[int] = None) -> HttpJudge:
    provider = os.getenv("JUDGE_PROVIDER", "").strip().lower()
    if provider != "openrouter":
        raise JudgeNotConfigured("Set JUDGE_PROVIDER=openrouter in .env: only OpenRouter free models are supported for judging.")
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        raise JudgeNotConfigured("OPENROUTER_API_KEY is not set in .env.")
    model = os.getenv("JUDGE_MODEL", "").strip() or DEFAULT_MODEL
    require_free_model(model)
    env_budget = os.getenv("JUDGE_MAX_CALLS", "").strip()
    return HttpJudge(
        model, key,
        min_interval=float(os.getenv("JUDGE_MIN_INTERVAL", DEFAULT_MIN_INTERVAL)),
        max_calls=max_calls if max_calls is not None else (int(env_budget) if env_budget else None),
    )
