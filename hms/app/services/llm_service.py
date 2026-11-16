import os
import time
import logging
from typing import Callable, List, Dict, Any, Optional
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Primary Gemini Cloud API endpoints
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEPRECATED_OR_INVALID_MODELS = {"gemini-3.1-flash-lite", "gemini-2.5-pro", "gemini-2.5-flash-lite"}
MAX_TOOL_ROUNDS = 3  # how many times the model may ask for data before it must answer


def get_effective_gemini_model(model_override: Optional[str] = None) -> str:
    """Returns an active, verified Gemini Cloud model, bypassing deprecated models."""
    candidate = model_override or os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"
    if candidate in DEPRECATED_OR_INVALID_MODELS:
        return "gemini-3.5-flash-lite"
    return candidate


def get_gemini_api_key() -> Optional[str]:
    """Retrieves the Google Gemini Cloud API key (GEMINI_API_KEY or GOOGLE_API_KEY)."""
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not key or key.startswith("your_"):
        return None
    return key


def _record_usage(usage: Optional[Dict[str, Any]], data: Dict[str, Any], model: str, primary_model: str, started: float) -> None:
    """Fills the caller's `usage` dict; token counts add up across the requests of one tool-using answer."""
    if usage is None:
        return
    meta = data.get("usageMetadata", {})

    def add(key: str, value: Optional[int]) -> Optional[int]:
        return (usage.get(key) or 0) + (value or 0) if value is not None or usage.get(key) is not None else None

    usage.update({
        "model": model,
        "latency_s": round(time.perf_counter() - started, 3),
        "prompt_tokens": add("prompt_tokens", meta.get("promptTokenCount")),
        "output_tokens": add("output_tokens", meta.get("candidatesTokenCount")),
        "total_tokens": add("total_tokens", meta.get("totalTokenCount")),
        "fallback_used": model != primary_model or bool(usage.get("fallback_used")),
        "requests": (usage.get("requests") or 0) + 1,
    })


def _post_with_fallback(payload: Dict[str, Any], cloud_models: List[str], primary_model: str, api_key: str,
                        usage: Optional[Dict[str, Any]], started: float) -> List[Dict[str, Any]]:
    """
    Sends one generateContent request, trying the backup models if one is overloaded (429/503), times out or answers
    nothing. Returns the `parts` of the reply. Raises HTTPException 503 if every model fails.
    """
    last_error_msg = None
    timeout_config = httpx.Timeout(timeout=15.0, connect=6.0)

    for target_model in cloud_models:
        url = f"{GEMINI_API_BASE}/{target_model}:generateContent"
        try:
            with httpx.Client(timeout=timeout_config) as client:
                # Key goes in a header, not the URL, so it never shows up in request logs
                resp = client.post(url, json=payload, headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
                if resp.status_code == 200:
                    data = resp.json()
                    _record_usage(usage, data, target_model, primary_model, started)
                    candidates = data.get("candidates", [])
                    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                    if parts:
                        return parts
                    logger.warning(f"Gemini Cloud ({target_model}) returned empty candidates.")
                    continue
                else:
                    msg = _extract_error_message(resp)
                    logger.warning(f"Gemini Cloud ({target_model}) error {resp.status_code}: {msg}. Attempting next model...")
                    last_error_msg = msg
                    continue
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(f"Gemini Cloud ({target_model}) connection issue: {e}. Attempting next model...")
            last_error_msg = str(e)
            continue

    # If all models in the pool were exhausted (upstream error is logged, not sent to the client)
    logger.error(f"All Gemini models failed. Last error: {last_error_msg or 'Request timed out'}")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The AI Concierge is temporarily unavailable. Please try again in a few moments."
    )


def _text_of(parts: List[Dict[str, Any]]) -> str:
    text_parts = [p["text"] for p in parts if "text" in p and not p.get("thought", False)]
    if text_parts:
        return "".join(text_parts).strip()
    return parts[0]["text"].strip() if parts and "text" in parts[0] else ""


def call_gemini_cloud_api(
    prompt: str,
    system_instruction: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    model: Optional[str] = None,
    usage: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_runner: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
) -> str:
    """
    Directly calls the Google Gemini REST Cloud API.
    If the requested model is busy (503 High Demand, 429 rate limit) or times out, it automatically tries
    backup official Gemini Cloud models.
    If all cloud models are unavailable, it raises HTTPException(status_code=503).
    NO fake hardcoded responses or invented data.
    If a `usage` dict is passed it is filled with the model used, latency and token counts (for evaluation/tracing).

    Tool use (structured RAG): when `tools` (Gemini function declarations) and `tool_runner(name, args) -> dict` are given,
    the model may answer with function calls instead of text. Each call is run by `tool_runner`, the results are sent back,
    and this repeats up to `max_tool_rounds` times; after that the model is told to answer with what it has. A question that
    needs no lookup still costs exactly one request. Token counts in `usage` add up over all requests.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Concierge service is currently offline: Google Gemini Cloud API key is not configured. Please configure a valid API key in settings."
        )

    primary_model = get_effective_gemini_model(model)

    # Candidate active models on Google Cloud in order of resilience and speed
    cloud_models = [primary_model]
    for backup_m in ["gemini-3.5-flash-lite", "gemini-3.5-flash"]:
        if backup_m not in cloud_models and backup_m not in DEPRECATED_OR_INVALID_MODELS:
            cloud_models.append(backup_m)

    # Build multi-turn contents
    contents: List[Dict[str, Any]] = []
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = "user" if turn.get("role") == "user" else "model"
            text_content = turn.get("content", "")
            if text_content:
                contents.append({
                    "role": role,
                    "parts": [{"text": text_content}]
                })

    contents.append({
        "role": "user",
        "parts": [{"text": prompt}]
    })

    payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    use_tools = bool(tools and tool_runner)
    if use_tools:
        payload["tools"] = tools

    started = time.perf_counter()
    rounds = 0
    while True:
        parts = _post_with_fallback(payload, cloud_models, primary_model, api_key, usage, started)
        calls = [p for p in parts if "functionCall" in p] if use_tools else []
        if not calls:
            return _text_of(parts)

        if rounds >= max_tool_rounds:
            # Out of rounds: forbid further calls and ask for the final answer from what has been gathered
            payload["toolConfig"] = {"functionCallingConfig": {"mode": "NONE"}}
            if rounds == max_tool_rounds:
                rounds += 1
                continue
            return _text_of(parts)

        rounds += 1
        # The model's own reply is echoed back unchanged (Gemini 3 needs its "thoughtSignature" returned with the call)
        contents.append({"role": "model", "parts": parts})
        responses = []
        for part in calls:
            call = part["functionCall"]
            try:
                result = tool_runner(call.get("name", ""), call.get("args") or {})
            except Exception:  # a broken tool must not take the whole answer down: tell the model and let it carry on
                logger.exception("tool runner failed for %s", call.get("name"))
                result = {"ok": False, "error": "the lookup failed"}
            reply = {"name": call.get("name", ""), "response": result}
            if call.get("id"):
                reply["id"] = call["id"]
            responses.append({"functionResponse": reply})
        contents.append({"role": "user", "parts": responses})
        payload["contents"] = contents
        if usage is not None:
            usage["tool_rounds"] = rounds


def _extract_error_message(resp: httpx.Response) -> str:
    """Pulls the error message out of a Gemini error response, tolerating non-JSON bodies."""
    try:
        return resp.json().get("error", {}).get("message") or f"Status {resp.status_code}"
    except ValueError:
        return resp.text[:200] or f"Status {resp.status_code}"
