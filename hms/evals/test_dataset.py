"""The golden dataset is itself checked against the seed, so a typo or stale label can't silently corrupt scores."""
from collections import Counter

import pytest

from app.models.document import HotelDocumentChunk
from evals.dataset import BEHAVIORS, CATEGORIES, USER_EMAILS, Case, check_answer, load_golden
from evals.seed import HOTELS, STAFF_ONLY_CANARY, sid

CASES = load_golden()


def test_dataset_has_enough_variety():
    assert len(CASES) >= 60
    counts = Counter(c.category for c in CASES)
    assert set(counts) == CATEGORIES, f"categories without cases: {CATEGORIES - set(counts)}"
    assert all(n >= 2 for n in counts.values())


def test_ids_are_unique():
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case_is_well_formed(case: Case):
    assert case.category in CATEGORIES and case.behavior in BEHAVIORS
    assert case.user == "anonymous" or case.user in USER_EMAILS
    assert case.hotel is None or case.hotel in HOTELS
    assert case.question.strip() and case.expected_facts
    assert all(t["role"] in ("user", "assistant") and t["content"].strip() for t in case.history)
    assert all(isinstance(g, list) and g for g in case.must_contain)
    assert all(r["hotel"] in HOTELS and r["contains"] for r in case.relevant)


@pytest.mark.parametrize("case", [c for c in CASES if c.relevant], ids=lambda c: c.id)
def test_retrieval_labels_match_real_public_chunks(db, case: Case):
    """Every `relevant` label must point at text that really exists in a public chunk of that hotel."""
    for rel in case.relevant:
        chunks = db.query(HotelDocumentChunk).filter(
            HotelDocumentChunk.hotel_id == sid(f"hotel:{rel['hotel']}"),
            HotelDocumentChunk.access_level == "public",
            HotelDocumentChunk.deleted_at.is_(None),
        ).all()
        assert any(rel["contains"].lower() in c.content.lower() for c in chunks), \
            f"{case.id}: no public chunk of {rel['hotel']} contains {rel['contains']!r}"


def test_hotel_scoped_relevance_labels_stay_inside_the_scoped_hotel():
    for c in CASES:
        if c.hotel and c.category in ("policy", "faq"):
            assert all(r["hotel"] == c.hotel for r in c.relevant), c.id


def test_forbidden_strings_are_not_part_of_a_correct_answer():
    """A forbidden string must never also be a required one."""
    for c in CASES:
        required = {alt.lower() for g in c.must_contain for alt in g}
        assert not required & {f.lower() for f in c.forbidden}, c.id


def test_security_cases_forbid_the_canary_or_secrets():
    sec = [c for c in CASES if c.category == "security"]
    assert any(STAFF_ONLY_CANARY in c.forbidden for c in sec)
    assert all(c.forbidden for c in sec)


# ---- the deterministic checker itself
def test_check_answer_accepts_alternatives_and_is_case_insensitive():
    case = next(c for c in CASES if c.id == "pol-checkin-mayfair")
    assert check_answer(case, "Check-in is at 3 pm and check-out is at 11 AM.") == []
    assert check_answer(case, "Check-in is at 3 PM.") == [f"missing one of {case.must_contain[1]}"]


def test_check_answer_flags_forbidden_text():
    case = next(c for c in CASES if c.id == "sec-staff-canary")
    assert check_answer(case, f"The code is {STAFF_ONLY_CANARY.lower()}")
    assert check_answer(case, "I cannot share that.") == []


# ---- structured RAG fields
from evals.dataset import TOOLS, check_tools  # noqa: E402


def test_structured_cases_exist_and_name_real_tools():
    structured = [c for c in CASES if c.category == "structured"]
    assert len(structured) >= 12
    for c in CASES:
        for expected in c.expected_tools:
            assert all(name in TOOLS for name in expected.split("|")), (c.id, expected)


def test_text_questions_cannot_also_expect_a_lookup():
    for c in CASES:
        assert not (c.forbid_tools and c.expected_tools), c.id
    assert {"policy", "faq", "refund"} <= {c.category for c in CASES if c.forbid_tools}


def test_every_structured_answer_case_declares_the_lookup_it_needs():
    exceptions = {"st-avail-missing-dates", "st-avail-past-date"}      # these should be answered WITHOUT a successful lookup
    for c in CASES:
        if c.category == "structured" and c.id not in exceptions:
            assert c.expected_tools, c.id


def _call(name, ok=True):
    return {"name": name, "ok": ok, "rows": 1, "args": {}}


def test_check_tools_accepts_alternatives_and_requires_success():
    case = next(c for c in CASES if c.id == "st-best-rated")                       # needs search_hotels OR catalog_stats
    assert check_tools(case, [_call("catalog_stats")]) == []
    assert check_tools(case, [_call("search_hotels")]) == []
    assert check_tools(case, [])                                                     # no lookup at all
    assert check_tools(case, [_call("search_hotels", ok=False)])                     # a failed lookup does not count
    assert check_tools(case, [_call("check_availability")])                          # the wrong tool


def test_check_tools_flags_lookups_on_text_questions():
    case = next(c for c in CASES if c.id == "pol-pets-mayfair")
    assert check_tools(case, []) == []
    assert "should be answered from context" in check_tools(case, [_call("search_hotels")])[0]
