"""What the chatbot is allowed to know: booking data is per-user, knowledge search respects access levels and hotel scope."""
import pytest

from app.models.user import User
from app.services import chat_service, document_service
from evals.seed import FROZEN_NOW, STAFF_ONLY_CANARY, sid


def _context(db, email):
    user = db.query(User).filter(User.email == email).first() if email else None
    return chat_service.build_user_booking_context(db, user, now=FROZEN_NOW)[0]


def test_visitor_context_contains_no_reservation_data(db):
    text = _context(db, None).lower()
    for secret in ("mayfair", "aspen", "shibuya", "total paid", "reservation id", "marcus", "sophia"):
        assert secret not in text


def test_each_guest_only_sees_their_own_reservations(db):
    marcus, sophia = _context(db, "marcus.vance@test.hms"), _context(db, "sophia.carter@test.hms")
    assert "Mayfair" in marcus and "Shibuya" not in marcus and "sophia" not in marcus.lower()
    assert "Shibuya" in sophia and "Mayfair" not in sophia and "marcus" not in sophia.lower()


def test_context_uses_the_pinned_clock_and_the_hotels_own_checkin_time(db):
    # 10 days after the frozen "now" (12:00), at Mayfair's published 3:00 PM check-in = 243 hours
    assert "Notice Prior to Check-in: 243.0 hours" in _context(db, "marcus.vance@test.hms")
    # Shibuya publishes 2:00 PM: 1 day later at 14:00 = 26 hours
    assert "Notice Prior to Check-in: 26.0 hours" in _context(db, "sophia.carter@test.hms")


def test_completed_stays_are_not_refundable(db):
    assert "Check-in time has already passed" in _context(db, "marcus.vance@test.hms")


def test_catalog_scoped_to_one_hotel_excludes_the_others(db):
    text = chat_service.build_hotel_catalog_context(db, target_hotel_id=sid("hotel:aspen"))
    assert "Aspen Lodge" in text and "Mayfair" not in text and "Shibuya" not in text


@pytest.mark.parametrize("hotel", ["mayfair", "aspen", "shibuya"])
def test_public_search_is_limited_to_public_chunks_of_the_requested_hotel(db, hotel):
    hits = document_service.search_chunks(db, "check-in time and breakfast and pets", hotel_id=sid(f"hotel:{hotel}"), top_k=20)
    assert hits
    assert all(h["hotel_id"] == sid(f"hotel:{hotel}") for h in hits)
    assert not any(STAFF_ONLY_CANARY in h["content"] for h in hits)


def test_unscoped_search_still_hides_staff_only_chunks(db):
    hits = document_service.search_chunks(db, "master key override code night safe memo", top_k=50)
    assert not any(STAFF_ONLY_CANARY in h["content"] for h in hits)


def test_debug_payload_exposes_what_the_model_saw(db, monkeypatch):
    """Phase 0 instrumentation: retrieved chunks, prompt and token usage are returned only when debug=True."""
    from app.services import llm_service

    def fake_gemini(prompt, system_instruction=None, conversation_history=None, temperature=0.3, usage=None, **kw):
        usage.update({"model": "fake-model", "prompt_tokens": 10, "output_tokens": 5, "total_tokens": 15})
        return "The Mayfair welcomes dogs and cats."

    monkeypatch.setattr(llm_service, "call_gemini_cloud_api", fake_gemini)
    user = db.query(User).filter(User.email == "marcus.vance@test.hms").first()

    plain = chat_service.send_chat_message(db, "Are pets allowed?", user=user, hotel_id=sid("hotel:mayfair"), now=FROZEN_NOW)
    assert "debug" not in plain

    result = chat_service.send_chat_message(db, "Are pets allowed?", user=user, hotel_id=sid("hotel:mayfair"), debug=True, now=FROZEN_NOW)
    dbg = result["debug"]
    assert dbg["llm"]["model"] == "fake-model" and dbg["llm"]["total_tokens"] == 15 and "total_latency_s" in dbg["llm"]
    assert any("pet" in c["content"].lower() for c in dbg["retrieved_chunks"])
    assert "GRANDSTAY VERIFIED PROPERTIES" in dbg["system_instruction"]
    assert STAFF_ONLY_CANARY not in dbg["system_instruction"]


# ---------------- the check-in time is read from the hotel, never assumed ----------------
from datetime import date, datetime, time, timezone  # noqa: E402


@pytest.mark.parametrize("text,expected", [
    ("Check-in is from 3:00 PM and check-out is at 11:00 AM.", time(15, 0)),
    ("Check-in begins at 3:00 PM local time. Early check-in from 11:00 AM is available.", time(15, 0)),
    ("Early check-in from 11:00 AM is available. Check-in begins at 4 PM.", time(16, 0)),
    ("Check-in: 12:30 pm. Check-out 11 am.", time(12, 30)),
    ("Check-in is at 12:00 AM", time(0, 0)),
    ("Check-in from 15:00, check-out by 11:00.", time(15, 0)),
    ("Check-out is at 11:00 AM.", None),
    ("Guests are welcome any time.", None),
    ("", None),
])
def test_parse_checkin_time(text, expected):
    assert chat_service.parse_checkin_time([text]) == expected


def test_parse_checkin_time_uses_the_first_policy_that_states_one():
    assert chat_service.parse_checkin_time(["No pets.", "Check-in is from 4:00 PM."]) == time(16, 0)


NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def test_notice_is_unknown_when_no_checkin_time_is_published():
    assert chat_service.notice_hours_before_checkin(date(2026, 11, 11), None, NOW) is None
    assert chat_service.notice_hours_before_checkin(date(2026, 11, 1), None, NOW) is None


def test_a_checkin_date_in_the_past_is_certain_even_without_a_time():
    assert chat_service.notice_hours_before_checkin(date(2026, 10, 31), None, NOW) < 0


def test_notice_with_a_published_time():
    assert chat_service.notice_hours_before_checkin(date(2026, 11, 2), time(14, 0), NOW) == 26.0


def test_hotel_without_a_published_checkin_time_gets_no_made_up_refund_figure(db):
    from app.models.policy import Policy
    pol = db.query(Policy).filter(Policy.hotel_id == sid("hotel:mayfair"), Policy.policy_type == "check_in_check_out").one()
    original = pol.description
    pol.description = "Check-out is at 11:00 AM. Late check-out until 2:00 PM is subject to availability."
    db.flush()
    try:
        text = _context(db, "marcus.vance@test.hms")
        assert "this hotel has not published a check-in time" in text
        assert "cannot be calculated exactly" in text
        assert "Calculated Refund Eligibility if Cancelled: $" not in text.split("Aspen")[0]  # Mayfair block has no figure
    finally:
        pol.description = original
        db.flush()
        db.rollback()


def test_the_whole_chunk_reaches_the_prompt_not_just_its_start(monkeypatch):
    """Chunks used to be cut at 350 characters: most uploaded-document chunks (~560) and the reviews chunk lost their end,
    even when that end was why search picked them. The seed data has no chunk that long, so this test supplies one."""
    tail = "Late checkout until 2 PM is free for members."
    long_chunk = {
        "hotel_name": "GrandStay Mayfair", "content": ("Our concierge desk is staffed day and night.\n" * 12) + tail,
        "metadata": {"title": "House rules"}, "source_type": "document", "similarity_score": 0.7, "rerank_score": 0.9,
    }
    assert len(long_chunk["content"]) > 500
    monkeypatch.setattr(document_service, "search_chunks", lambda **kw: [long_chunk])

    prompt_text, citations, _ = chat_service.build_knowledge_base_context(None, query="late checkout", top_k=8)
    assert tail in prompt_text
    assert "\n" not in prompt_text.split("]: ", 1)[1]  # line breaks inside a chunk are flattened to spaces
    assert len(citations[0]["snippet"]) <= 200 and citations[0]["relevance_score"] == 0.9
