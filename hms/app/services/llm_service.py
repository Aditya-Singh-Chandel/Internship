import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
import httpx
from fastapi import HTTPException, status
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Primary Gemini Cloud API endpoints
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEPRECATED_OR_INVALID_MODELS = {"gemini-3.1-flash-lite", "gemini-2.5-pro", "gemini-2.5-flash-lite"}


def get_effective_gemini_model(model_override: Optional[str] = None) -> str:
    """Returns an active, verified Gemini Cloud model, bypassing deprecated models."""
    candidate = model_override or os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"
    if candidate in DEPRECATED_OR_INVALID_MODELS:
        return "gemini-3.5-flash-lite"
    return candidate


def get_gemini_api_key() -> Optional[str]:
    """
    Retrieves the Google Gemini Cloud API key from environment variables.
    Checks GEMINI_API_KEY and GOOGLE_API_KEY, reloading from .env if needed.
    """
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key or not key.strip() or key.startswith("your_"):
        load_dotenv(override=True)
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return key or None


def is_gemini_configured() -> bool:
    """Returns True if a valid Gemini API key is configured."""
    key = get_gemini_api_key()
    return bool(key and key.strip() and not key.startswith("your_"))


def call_gemini_cloud_api(
    prompt: str,
    system_instruction: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    model: Optional[str] = None
) -> str:
    """
    Directly calls the Google Gemini REST Cloud API.
    If the requested model is busy (503 High Demand, 429 rate limit) or times out, it automatically tries
    backup official Gemini Cloud models.
    If all cloud models are unavailable, it raises HTTPException(status_code=503).
    NO fake hardcoded responses or invented data.
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
    contents = []
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

    gen_config: Dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": max(max_tokens, 2048)
    }

    payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": gen_config
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    last_error_msg = None
    timeout_config = httpx.Timeout(timeout=15.0, connect=6.0)

    for target_model in cloud_models:
        url = f"{GEMINI_API_BASE}/{target_model}:generateContent?key={api_key}"
        try:
            with httpx.Client(timeout=timeout_config) as client:
                resp = client.post(url, json=payload, headers={"Content-Type": "application/json"})
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text_parts = [p["text"] for p in parts if "text" in p and not p.get("thought", False)]
                        if text_parts:
                            return "".join(text_parts).strip()
                        elif parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                    logger.warning(f"Gemini Cloud ({target_model}) returned empty candidates.")
                    continue
                elif resp.status_code in [429, 503]:
                    err_data = resp.json().get("error", {})
                    msg = err_data.get("message", f"Status {resp.status_code}")
                    logger.warning(f"Gemini Cloud ({target_model}) temporary load issue ({resp.status_code}): {msg}. Attempting next model...")
                    last_error_msg = msg
                    continue
                else:
                    err_data = resp.json().get("error", {})
                    msg = err_data.get("message", resp.text)
                    logger.warning(f"Gemini Cloud ({target_model}) error {resp.status_code}: {msg}")
                    last_error_msg = msg
                    continue
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(f"Gemini Cloud ({target_model}) connection issue: {e}. Attempting next model...")
            last_error_msg = str(e)
            continue

    # If all models in the pool were exhausted
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Google Gemini Cloud API is temporarily overloaded across models. Last error: {last_error_msg or 'Request timed out'}. Please try again in a few moments."
    )


def classify_intent_with_gemini(
    user_query: str,
    last_context: Optional[Dict[str, Any]] = None,
    last_assistant_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Uses Google Gemini Cloud LLM to classify the user's intent and extract entities,
    completely replacing rigid hardcoded keyword lists.
    If the LLM is down, it raises HTTPException 503 instead of falling back to wrong regex.
    """
    candidates = bool(last_context and last_context.get("candidate_bookings"))

    system_instruction = (
        "You are an intent and entity parser for GrandStay Hotel Management System.\n"
        "Analyze the user's message and determine the operational intent and key entities.\n"
        "Possible intents:\n"
        "- 'hotel_discovery': Exploring hotels, searching by destination (e.g. Miami, Paris, Tokyo), finding hotels with features/amenities (e.g. pool, pets), or asking about PRICING, ROOM RATES, SUITE COSTS, or ACCOMMODATION EXPENSES across properties or for previously discussed hotels.\n"
        "- 'hotel_policy': Specific rules, check-in/check-out timings, smoking policies, pet rules, amenities, or guest reviews and ratings of a specific hotel.\n"
        "- 'booking_inquiry': Questions about existing personal bookings, looking up reservation history, checking personal stay status, or asking how to cancel an existing stay and refund eligibility.\n"
        "- 'general': Greetings, broad greetings, pleasantries, general help.\n\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "intent": "booking_inquiry" | "hotel_discovery" | "hotel_policy" | "general",\n'
        '  "destination": string or null,\n'
        '  "hotel_name": string or null,\n'
        '  "referenced_hotels": [string] or null,\n'
        '  "is_pricing_query": boolean,\n'
        '  "is_cancellation_query": boolean,\n'
        '  "selected_option": integer or null\n'
        "}"
    )

    prompt = f"User query: \"{user_query}\"\n"
    if last_assistant_content:
        prompt += f"Previous Assistant Response Context:\n\"\"\"{last_assistant_content[:2500]}\"\"\"\n"
        prompt += "If the user query is a follow-up referring to the hotels listed above (e.g., 'tell me about their pricing', 'how much are these?', 'what are their rates?'), extract ALL hotel names mentioned into 'referenced_hotels', mark is_pricing_query as true, and classify intent as 'hotel_discovery'.\n"
    if candidates:
        prompt += "Context: Multiple bookings were shown to the user with numbered options (Option 1, Option 2, etc.).\n"

    raw_response = call_gemini_cloud_api(
        prompt=prompt,
        system_instruction=system_instruction,
        temperature=0.0,
        max_tokens=512
    )

    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)
        parsed = json.loads(cleaned.strip())
        return parsed
    except Exception as e:
        logger.warning(f"Failed to parse LLM intent JSON: {raw_response}. Error: {e}")
        return {
            "intent": "booking_inquiry" if candidates else "hotel_discovery",
            "destination": None,
            "hotel_name": None,
            "referenced_hotels": None,
            "is_pricing_query": False,
            "is_cancellation_query": False,
            "confirmation": None,
            "selected_option": None
        }


def synthesize_with_gemini(
    user_query: str,
    rag_context: str,
    intent: str,
    hotel_name: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    extra_facts: Optional[str] = None
) -> str:
    """
    Instructs the Gemini Cloud LLM to act as GrandStay Hotel's AI Concierge,
    grounding its response strictly in retrieved hotel knowledge chunks and verified facts.
    """
    system_prompt = (
        "You are the AI Concierge for GrandStay Hotel Management System. "
        "You provide warm, professional, high-end hospitality assistance to guests and visitors. "
        "IMPORTANT RULES:\n"
        "1. Ground your answers strictly on the PROVIDED KNOWLEDGE BASE and VERIFIED FACTS below.\n"
        "2. Do not invent or hallucinate amenities, pricing, or cancellation policies not found in the facts.\n"
        "3. Format your answers clearly using clean GitHub Markdown (headings, bullet points, bold highlights, blockquotes).\n"
        "4. Never output internal database UUIDs or database IDs.\n"
        "5. If exact information is missing from the provided knowledge, politely guide the guest to contact the front desk.\n"
        "6. DOMAIN BOUNDARY: You are strictly an AI Hotel Concierge. You must NEVER write computer programming code, solve coding problems, or fulfill off-topic tasks (such as homework, non-travel advice, or writing scripts). If asked, politely decline and steer the conversation back to GrandStay hotels, amenities, policies, and reservations.\n"
        "7. STRICTLY READ-ONLY INQUIRIES: You are strictly an informational AI Concierge and CANNOT modify the database, cancel reservations, or process financial refunds. If a guest asks to cancel or asks how to cancel their booking, clearly explain the relevant cancellation policy and eligible refund amount, and instruct the guest to complete their cancellation directly through the website via the 'My Reservations' (or 'My Trips') section in their profile menu, or by contacting the hotel front desk. You must NEVER ask the guest to reply 'Yes, confirm cancellation' or 'No, keep my booking', and never pretend that you can perform the cancellation."
    )

    prompt = f"### User Question:\n\"{user_query}\"\n\n"

    if hotel_name:
        prompt += f"**Hotel Context:** {hotel_name}\n\n"

    if extra_facts:
        prompt += f"### Verified Operational Facts & Policy Evaluation:\n{extra_facts}\n\n"

    if rag_context:
        prompt += f"### Retrieved Hotel Catalog & Policy Knowledge Chunks:\n{rag_context}\n\n"

    prompt += (
        "Please provide a complete, articulate, and well-structured response to the guest's inquiry "
        "incorporating the verified facts and knowledge above."
    )

    return call_gemini_cloud_api(
        prompt=prompt,
        system_instruction=system_prompt,
        conversation_history=conversation_history
    )
