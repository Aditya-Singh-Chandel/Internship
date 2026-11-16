"""evaluate_dynamic_cancellation_policy: the chatbot quotes refunds from this, so every tier must be exact."""
import pytest

from app.services.chat_service import evaluate_dynamic_cancellation_policy as refund
from evals.seed import HOTELS

MAYFAIR = HOTELS["mayfair"]["policies"]["cancellation"]    # 100% >= 72h, 50% 24-72h, 0% < 24h
ASPEN = HOTELS["aspen"]["policies"]["cancellation"]        # "Full refund" >= 7 days, else non-refundable
SHIBUYA = HOTELS["shibuya"]["policies"]["cancellation"]    # 100% >= 48h, else non-refundable

# Real production text: all tiers written in ONE paragraph, and "Full refund" without a percent sign
PEAK_SEASON_ONE_PARAGRAPH = (
    "Peak Season Policy: Full refund for cancellations made at least 72 hours prior to scheduled 3:00 PM check-in. "
    "50% refund between 24-72 hours. Non-refundable under 24 hours."
)


@pytest.mark.parametrize("policy,hours,expected", [
    (MAYFAIR, 200, 1.0), (MAYFAIR, 72, 1.0), (MAYFAIR, 71.9, 0.5), (MAYFAIR, 24, 0.5), (MAYFAIR, 23.9, 0.0),
    (ASPEN, 400, 1.0), (ASPEN, 168, 1.0), (ASPEN, 167.9, 0.0), (ASPEN, 24, 0.0),
    (SHIBUYA, 100, 1.0), (SHIBUYA, 48, 1.0), (SHIBUYA, 47.9, 0.0),
    (PEAK_SEASON_ONE_PARAGRAPH, 100, 1.0), (PEAK_SEASON_ONE_PARAGRAPH, 72, 1.0),
    (PEAK_SEASON_ONE_PARAGRAPH, 50, 0.5), (PEAK_SEASON_ONE_PARAGRAPH, 24, 0.5), (PEAK_SEASON_ONE_PARAGRAPH, 10, 0.0),
])
def test_refund_tiers(policy, hours, expected):
    pct, _reason = refund(policy, hours_until_checkin=hours, total_amount=1000.0)
    assert pct == expected


@pytest.mark.parametrize("hours", [0, -1, -500])
def test_stay_already_started_is_never_refundable(hours):
    pct, reason = refund(MAYFAIR, hours_until_checkin=hours, total_amount=1000.0)
    assert pct == 0.0 and "already" in reason.lower()


@pytest.mark.parametrize("hours,expected", [(60, 1.0), (30, 0.5), (5, 0.0)])
def test_policy_without_parsable_tiers_uses_48h_24h_default(hours, expected):
    pct, _ = refund("Please contact the front desk about cancellations.", hours_until_checkin=hours, total_amount=500.0)
    assert pct == expected


def test_reason_mentions_the_percentage_given():
    _pct, reason = refund(MAYFAIR, hours_until_checkin=48, total_amount=1000.0)
    assert "50%" in reason


@pytest.mark.parametrize("text", ["This rate is non-refundable.", "All bookings are non-refundable and cannot be changed."])
def test_blanket_non_refundable_rate_is_never_refunded(text):
    pct, _ = refund(text, hours_until_checkin=500, total_amount=1000.0)
    assert pct == 0.0


@pytest.mark.parametrize("text,hours,expected", [
    ("1. 100% refund if cancelled 14 days before arrival\n2. 50% refund 7 to 14 days before\n3. No refund inside 7 days", 400, 1.0),
    ("1. 100% refund if cancelled 14 days before arrival\n2. 50% refund 7 to 14 days before\n3. No refund inside 7 days", 200, 0.5),
    ("1. 100% refund if cancelled 14 days before arrival\n2. 50% refund 7 to 14 days before\n3. No refund inside 7 days", 100, 0.0),
    ("* 75% refund with 5+ days notice\n* 0% refund otherwise", 130, 0.75),
])
def test_numbered_and_bulleted_policies(text, hours, expected):
    assert refund(text, hours_until_checkin=hours, total_amount=1000.0)[0] == expected
