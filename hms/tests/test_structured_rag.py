"""
Structured RAG tools, checked against hand-computed answers from the seed data (evals/seed.py):

  hotels      Mayfair (London)  rooms: Classic King $450 x5, Mayfair Suite $980 sleeps 4 x2   rating 4.5 (5,4)
              Aspen Lodge       rooms: Alpine Queen $620 x6, Summit Suite $1450 sleeps 5 x1   rating 3.5 (4,3)
              Shibuya (Tokyo)   rooms: Standard Twin $310 x8, Skyline Suite $820 sleeps 3 x1  rating 5.0 (5,5)
  bookings    Marcus: Mayfair Suite 11-11..11-14 (confirmed); Sophia: Skyline Suite 11-02..11-04 (confirmed)
  "today"     2026-11-01
"""
import json

import pytest

from app.models.hotel import Hotel
from app.services.structured_rag_service import MAX_ROWS, StructuredTools, TOOL_DECLARATIONS, _like
from evals.seed import FROZEN_NOW, sid


@pytest.fixture()
def tools(db):
    return StructuredTools(db, now=FROZEN_NOW)


def rows(result):
    assert result["ok"], result
    return result["rows"]


# ---------------- search_hotels ----------------
def test_hotels_ranked_by_true_average_rating(tools):
    result = tools.run("search_hotels", {"sort_by": "rating_desc"})
    assert [(r["hotel"], r["average_rating"], r["review_count"]) for r in rows(result)] == [
        ("GrandStay Shibuya", 5.0, 2), ("GrandStay Mayfair", 4.5, 2), ("GrandStay Aspen Lodge", 3.5, 2)]


def test_minimum_rating_filter(tools):
    assert [r["hotel"] for r in rows(tools.run("search_hotels", {"min_rating": 4, "sort_by": "rating_desc"}))] == ["GrandStay Shibuya", "GrandStay Mayfair"]


@pytest.mark.parametrize("args,expected", [
    ({"city": "Tokyo"}, ["GrandStay Shibuya"]),
    ({"country": "united kingdom"}, ["GrandStay Mayfair"]),
    ({"amenity": "spa"}, ["GrandStay Mayfair"]),
    ({"amenity": "onsen"}, ["GrandStay Shibuya"]),
    ({"amenity": "rooftop"}, ["GrandStay Mayfair", "GrandStay Shibuya"]),
    ({"amenity": "valet"}, ["GrandStay Aspen Lodge"]),
    ({"policy_keyword": "pet"}, ["GrandStay Aspen Lodge", "GrandStay Mayfair", "GrandStay Shibuya"]),
    ({"city": "Tokyo", "amenity": "spa"}, []),
])
def test_hotel_filters(tools, args, expected):
    assert sorted(r["hotel"] for r in rows(tools.run("search_hotels", args))) == expected


def test_hotel_rows_carry_price_and_amenities(tools):
    aspen = rows(tools.run("search_hotels", {"city": "Aspen"}))[0]
    assert aspen["lowest_nightly_price"] == 620.0 and "Ski Valet" in aspen["amenities"]


# ---------------- search_room_types ----------------
def test_rooms_under_a_price_sorted_cheapest_first(tools):
    found = rows(tools.run("search_room_types", {"max_price": 500}))
    assert [(r["room_type"], r["price_per_night"]) for r in found] == [("Standard Twin", 310.0), ("Classic King", 450.0)]


def test_cheapest_room_that_sleeps_four(tools):
    first = rows(tools.run("search_room_types", {"min_guests": 4}))[0]
    assert (first["hotel"], first["room_type"], first["price_per_night"], first["sleeps"]) == ("GrandStay Mayfair", "Mayfair Suite", 980.0, 4)


def test_rooms_at_one_hotel_most_expensive_first(tools):
    found = rows(tools.run("search_room_types", {"hotel_name": "Aspen", "sort_by": "price_desc"}))
    assert [r["room_type"] for r in found] == ["Summit Suite", "Alpine Queen"]


def test_room_amenity_filter_uses_the_hotel_amenities(tools):
    assert {r["hotel"] for r in rows(tools.run("search_room_types", {"amenity": "onsen"}))} == {"GrandStay Shibuya"}


# ---------------- check_availability ----------------
def avail(tools, hotel, room, checkin, checkout, **extra):
    result = tools.run("check_availability", {"hotel_name": hotel, "room_type_name": room, "checkin_date": checkin, "checkout_date": checkout, **extra})
    assert result["ok"], result
    return result["rows"][0]


def test_single_room_suite_is_sold_out_when_booked(tools):
    row = avail(tools, "Shibuya", "Skyline Suite", "2026-11-03", "2026-11-05")     # Sophia holds it 2-4 Nov
    assert (row["rooms_in_hotel"], row["rooms_available"], row["can_book_requested_rooms"]) == (1, 0, False)


def test_same_suite_is_free_on_other_dates(tools):
    row = avail(tools, "Shibuya", "Skyline Suite", "2026-11-10", "2026-11-12")
    assert row["rooms_available"] == 1 and row["can_book_requested_rooms"] is True
    assert row["estimated_total"] == 1640.0                                          # 820 x 2 nights


def test_checkout_day_is_not_a_night(tools):
    # Sophia checks out 4 Nov, so a stay starting 4 Nov is free
    assert avail(tools, "Shibuya", "Skyline Suite", "2026-11-04", "2026-11-06")["rooms_available"] == 1


def test_partially_booked_room_type_and_multi_room_requests(tools):
    one = avail(tools, "Mayfair", "Mayfair Suite", "2026-11-12", "2026-11-13")       # 2 rooms, Marcus holds 1
    assert (one["rooms_in_hotel"], one["rooms_available"], one["can_book_requested_rooms"]) == (2, 1, True)
    two = avail(tools, "Mayfair", "Mayfair Suite", "2026-11-12", "2026-11-13", rooms=2)
    assert two["can_book_requested_rooms"] is False and two["estimated_total"] == 980.0 * 1 * 2


def test_completed_and_past_stays_do_not_block_rooms(tools):
    assert avail(tools, "Aspen", "Alpine Queen", "2026-11-10", "2026-11-12")["rooms_available"] == 6


def test_availability_across_all_hotels_lists_bookable_first(tools):
    result = tools.run("check_availability", {"checkin_date": "2026-11-03", "checkout_date": "2026-11-05"})
    found = rows(result)
    assert len(found) == 6 and result["nights"] == 2
    assert found[-1]["room_type"] == "Skyline Suite" and found[-1]["can_book_requested_rooms"] is False   # sold-out goes last


def test_guest_count_filters_room_types(tools):
    found = rows(tools.run("check_availability", {"checkin_date": "2026-11-10", "checkout_date": "2026-11-12", "guests": 5}))
    assert [r["room_type"] for r in found] == ["Summit Suite"]


@pytest.mark.parametrize("args,message", [
    ({"checkin_date": "2026-10-15", "checkout_date": "2026-10-17"}, "in the past"),
    ({"checkin_date": "2026-11-05", "checkout_date": "2026-11-05"}, "after check-in"),
    ({"checkin_date": "2026-11-05", "checkout_date": "2026-11-01"}, "after check-in"),
    ({"checkin_date": "2026-11-05", "checkout_date": "2026-12-20"}, "limited to 30 nights"),
    ({"checkin_date": "next friday", "checkout_date": "2026-11-07"}, "YYYY-MM-DD"),
    ({"checkin_date": "2026-11-05"}, "YYYY-MM-DD"),
    ({"checkin_date": "2026-11-05", "checkout_date": "2026-11-07", "rooms": 50}, "between"),
])
def test_bad_availability_requests_are_explained_not_raised(tools, args, message):
    result = tools.run("check_availability", args)
    assert result["ok"] is False and message in result["error"]


def test_today_itself_is_bookable(tools):
    assert tools.run("check_availability", {"checkin_date": "2026-11-01", "checkout_date": "2026-11-02", "hotel_name": "Aspen"})["ok"]


# ---------------- catalog_stats ----------------
def stat(tools, **args):
    result = tools.run("catalog_stats", args)
    assert result["ok"], result
    return {r["group"]: (r["value"], r["based_on"]) for r in result["rows"]}


def test_hotel_counts(tools):
    assert stat(tools, metric="hotel_count") == {"all": (3.0, 3)}
    assert stat(tools, metric="hotel_count", group_by="country") == {"Japan": (1.0, 1), "United Kingdom": (1.0, 1), "United States": (1.0, 1)}


def test_average_price_per_city_and_overall_extremes(tools):
    assert stat(tools, metric="avg_price", group_by="city")["Tokyo"] == (565.0, 2)       # (310 + 820) / 2
    assert stat(tools, metric="min_price") == {"all": (310.0, 6)}
    assert stat(tools, metric="max_price") == {"all": (1450.0, 6)}


def test_average_rating_per_hotel_and_overall(tools):
    assert stat(tools, metric="avg_rating", group_by="hotel") == {"GrandStay Shibuya": (5.0, 2), "GrandStay Mayfair": (4.5, 2), "GrandStay Aspen Lodge": (3.5, 2)}
    assert stat(tools, metric="avg_rating") == {"all": (4.33, 6)}                        # (5+4+4+3+5+5) / 6


def test_room_type_counts(tools):
    assert set(stat(tools, metric="room_type_count", group_by="hotel").values()) == {(2.0, 2)}


def test_stats_need_a_valid_metric(tools):
    assert tools.run("catalog_stats", {})["ok"] is False
    assert tools.run("catalog_stats", {"metric": "drop_everything"})["ok"] is False


# ---------------- scoping, privacy, safety ----------------
def test_every_tool_respects_a_hotel_scoped_chat(db):
    scoped = StructuredTools(db, now=FROZEN_NOW, scope_hotel_id=sid("hotel:aspen"))
    assert [r["hotel"] for r in rows(scoped.run("search_hotels", {}))] == ["GrandStay Aspen Lodge"]
    assert {r["hotel"] for r in rows(scoped.run("search_room_types", {}))} == {"GrandStay Aspen Lodge"}
    assert {r["hotel"] for r in rows(scoped.run("check_availability", {"checkin_date": "2026-11-10", "checkout_date": "2026-11-12"}))} == {"GrandStay Aspen Lodge"}
    assert stat(scoped, metric="hotel_count") == {"all": (1.0, 1)}


def test_results_never_contain_guest_or_staff_data(tools):
    everything = [
        tools.run("search_hotels", {}), tools.run("search_room_types", {}),
        tools.run("check_availability", {"checkin_date": "2026-11-02", "checkout_date": "2026-11-04"}),
        tools.run("catalog_stats", {"metric": "avg_rating", "group_by": "hotel"}),
    ]
    text = json.dumps(everything)
    for secret in ("@", "Marcus", "Sophia", "Vance", "Carter", "STAFF-ONLY", "password", "Past Guest"):
        assert secret not in text


@pytest.mark.parametrize("evil", ["x'; DROP TABLE hotels; --", "' OR '1'='1", "Robert'); DROP TABLE users;--", "%", "_", "\\"])
def test_hostile_text_is_just_a_name_that_matches_nothing(tools, db, evil):
    for name, key in (("search_hotels", "city"), ("search_hotels", "amenity"), ("search_room_types", "hotel_name"), ("check_availability", "room_type_name")):
        args = {key: evil, "checkin_date": "2026-11-10", "checkout_date": "2026-11-12"}
        result = tools.run(name, args)
        assert result["ok"] and result["rows"] == [], (name, key, evil)
    assert db.query(Hotel).count() == 3          # nothing was dropped


def test_like_wildcards_are_escaped():
    assert _like("50%_off") == "%50\\%\\_off%"


def test_unknown_tools_and_unknown_arguments(tools):
    assert tools.run("run_sql", {"query": "select 1"})["ok"] is False
    assert tools.run("search_hotels", {"city": "Tokyo", "bogus": "ignored", "__class__": "x"})["ok"]


@pytest.mark.parametrize("args", [{"limit": 999}, {"limit": "many"}, {"min_rating": 9}, {"sort_by": "popularity"}])
def test_out_of_range_arguments_are_refused(tools, args):
    assert tools.run("search_hotels", args)["ok"] is False


def test_long_text_is_cut_and_row_count_is_capped(tools):
    assert tools.run("search_hotels", {"city": "a" * 5000})["ok"]
    assert StructuredTools._page([{}] * 25, MAX_ROWS) == {"count": 10, "truncated": True, "rows": [{}] * 10}


def test_calls_are_recorded_for_traces_and_history(tools):
    tools.run("search_hotels", {"city": "Tokyo"})
    tools.run("check_availability", {"checkin_date": "2020-01-01", "checkout_date": "2020-01-02"})
    assert [(c["name"], c["ok"], c["rows"]) for c in tools.calls] == [("search_hotels", True, 1), ("check_availability", False, 0)]
    assert tools.calls[1]["error"] and tools.calls[0]["ms"] >= 0


def test_the_menu_shown_to_the_model_matches_what_can_be_run(tools):
    declared = {d["name"] for group in TOOL_DECLARATIONS for d in group["functionDeclarations"]}
    assert declared == set(tools._handlers)
    for group in TOOL_DECLARATIONS:
        for d in group["functionDeclarations"]:
            assert d["description"] and d["parameters"]["type"] == "OBJECT"
