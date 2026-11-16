"""
Structured RAG for the AI concierge.

Plain RAG retrieves TEXT (documents) by meaning. Many guest questions are about STRUCTURED data and need exact answers:
"is the Skyline Suite free 3-5 November?", "cheapest room that sleeps 4", "best-rated hotel", "average price in Tokyo".
Similarity search cannot count, filter, rank or check dates, and pasting the whole catalog into the prompt does not scale.

Here the model is given a small menu of QUERY TOOLS. For a question it picks a tool and its arguments (Gemini function
calling); we run the matching vetted, parameterized database query and give the rows back; the model then writes the
answer from those rows. The model never writes SQL:

    guest question -> model picks tool + arguments -> validate -> parameterized query -> rows -> model answers from rows

Safety properties (each one is tested in tests/test_structured_rag.py):
  * read-only, public catalog data only: hotels, room types, prices, ratings, availability counts. No guests, no bookings,
    no e-mails. A guest's own reservations stay in the prompt, scoped by user, as before.
  * every argument is whitelisted, type-checked and range-limited; strings go to the database as bound parameters,
    with LIKE wildcards escaped, so "'; DROP TABLE hotels;--" is just a name that matches nothing.
  * results are capped (10 rows); dates must not be in the past; stays are limited to 30 nights.
  * when the chat is scoped to one hotel, every tool is scoped to that hotel too.
  * a bad call returns {"ok": false, "error": ...} for the model to explain; it never raises into the chat.
"""
import json
import logging
import time
import uuid
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core import tracing
from app.models.amenity import Amenity
from app.models.booking import Booking
from app.models.hotel import Hotel
from app.models.policy import Policy
from app.models.review import Review
from app.models.room_type import RoomType
from app.services.room_type_service import room_type_availability

logger = logging.getLogger(__name__)

MAX_ROWS = 10
MAX_STAY_NIGHTS = 30
MAX_ROOMS = 5
MAX_TEXT = 60


class ToolError(ValueError):
    """A problem with the model's arguments, explained to the model so it can ask the guest."""


# ------------------------------------------------------------------ what the model is told it can call
def _obj(properties: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    spec: Dict[str, Any] = {"type": "OBJECT", "properties": properties}
    if required:
        spec["required"] = required
    return spec


def _s(description: str, enum: Optional[List[str]] = None) -> Dict[str, Any]:
    spec: Dict[str, Any] = {"type": "STRING", "description": description}
    if enum:
        spec["enum"] = enum
    return spec


def _n(description: str, kind: str = "NUMBER") -> Dict[str, Any]:
    return {"type": kind, "description": description}


TOOL_DECLARATIONS: List[Dict[str, Any]] = [{"functionDeclarations": [
    {
        "name": "search_hotels",
        "description": "Find GrandStay hotels by city, country, amenity or policy, with their TRUE average guest rating "
                       "(over all reviews), review count, lowest room price and amenities. Use for 'which hotels ...', "
                       "'best rated', 'hotels in <place>', 'hotels with <amenity>'.",
        "parameters": _obj({
            "city": _s("City name, e.g. London"),
            "country": _s("Country name, e.g. Japan"),
            "amenity": _s("Amenity keyword, e.g. spa, pool, onsen, valet"),
            "policy_keyword": _s("Word in a hotel policy, e.g. pets, smoking, breakfast"),
            "min_rating": _n("Only hotels whose average rating is at least this (1-5)"),
            "sort_by": _s("Order of results", ["rating_desc", "rating_asc", "name", "price_asc"]),
            "limit": _n("Maximum rows (1-10)", "INTEGER"),
        }),
    },
    {
        "name": "search_room_types",
        "description": "Find room types by price, capacity, hotel or amenity, sorted by price. Use for 'cheapest room', "
                       "'rooms under $X', 'room that sleeps N', 'suites at <hotel>'. Prices are per night in USD.",
        "parameters": _obj({
            "hotel_name": _s("Hotel name or part of it, e.g. Aspen"),
            "min_price": _n("Minimum nightly price"),
            "max_price": _n("Maximum nightly price"),
            "min_guests": _n("Room must sleep at least this many guests", "INTEGER"),
            "amenity": _s("Amenity keyword offered by the room type or its hotel"),
            "sort_by": _s("Order of results", ["price_asc", "price_desc"]),
            "limit": _n("Maximum rows (1-10)", "INTEGER"),
        }),
    },
    {
        "name": "check_availability",
        "description": "Check how many rooms are free for a stay, per room type, with price and an estimated total. "
                       "ALWAYS use this for availability / sold-out / 'can I book' questions. Both dates are required: "
                       "if the guest has not given them, ask for them instead of calling.",
        "parameters": _obj({
            "checkin_date": _s("Check-in date, YYYY-MM-DD"),
            "checkout_date": _s("Check-out date, YYYY-MM-DD (the night before is the last night)"),
            "hotel_name": _s("Hotel name or part of it; omit to check every hotel"),
            "room_type_name": _s("Room type name or part of it, e.g. Skyline Suite"),
            "rooms": _n("Number of rooms wanted (1-5), default 1", "INTEGER"),
            "guests": _n("Number of guests that must fit in one room", "INTEGER"),
        }, ["checkin_date", "checkout_date"]),
    },
    {
        "name": "catalog_stats",
        "description": "Counts and averages across the catalog, grouped by city, country or hotel. Use for 'how many "
                       "hotels', 'average price in <city>', 'which country has the most hotels', 'average rating per hotel'.",
        "parameters": _obj({
            "metric": _s("What to compute", ["hotel_count", "room_type_count", "avg_price", "min_price", "max_price", "avg_rating"]),
            "group_by": _s("How to group", ["city", "country", "hotel", "all"]),
        }, ["metric"]),
    },
]}]


# ------------------------------------------------------------------ argument validation
def _like(value: str) -> str:
    """A LIKE pattern matching `value` anywhere; the guest's own % and _ are escaped so they stay literal."""
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _text(args: Dict[str, Any], key: str) -> Optional[str]:
    value = args.get(key)
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()[:MAX_TEXT]


def _number(args: Dict[str, Any], key: str, low: float, high: float) -> Optional[float]:
    value = args.get(key)
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{key} must be a number")
    if not low <= number <= high:
        raise ToolError(f"{key} must be between {low:g} and {high:g}")
    return number


def _integer(args: Dict[str, Any], key: str, low: int, high: int, default: Optional[int] = None) -> Optional[int]:
    number = _number(args, key, low, high)
    return default if number is None else int(number)


def _choice(args: Dict[str, Any], key: str, allowed: List[str], default: Optional[str] = None) -> Optional[str]:
    value = args.get(key)
    if value is None or value == "":
        return default
    if value not in allowed:
        raise ToolError(f"{key} must be one of {allowed}")
    return value


def _date(args: Dict[str, Any], key: str) -> date:
    value = args.get(key)
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ToolError(f"{key} must be a date in YYYY-MM-DD format")


def _num(value: Any, places: int = 2) -> Optional[float]:
    return None if value is None else round(float(value), places)


# ------------------------------------------------------------------ the executor
class StructuredTools:
    """Runs the tools for ONE chat message. `calls` records what was asked and returned (for traces, history, evals)."""

    declarations = TOOL_DECLARATIONS

    def __init__(self, db: Session, now: Optional[datetime] = None, scope_hotel_id: Optional[uuid.UUID] = None):
        self.db = db
        self.today = (now or datetime.now(timezone.utc)).date()
        self.scope_hotel_id = scope_hotel_id
        self.calls: List[Dict[str, Any]] = []
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "search_hotels": self._search_hotels,
            "search_room_types": self._search_room_types,
            "check_availability": self._check_availability,
            "catalog_stats": self._catalog_stats,
        }

    # ---- entry point used by the Gemini tool loop
    def run(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        began = time.perf_counter()
        args = args if isinstance(args, dict) else {}
        with tracing.span(f"tool_{name}", "TOOL", input=json.dumps(args, default=str)) as span:
            span.set("tool.name", name)
            span.set("tool.parameters", json.dumps(args, default=str))
            try:
                handler = self._handlers.get(name)
                if handler is None:
                    raise ToolError(f"unknown tool {name!r}; available: {sorted(self._handlers)}")
                # A SAVEPOINT: if the lookup fails, only its own work is undone, never the chat's pending message
                with self.db.begin_nested():
                    result = {"ok": True, "tool": name, **handler(args)}
            except ToolError as exc:
                result = {"ok": False, "tool": name, "error": str(exc)}
            except Exception:  # a broken lookup must never take the chat down
                logger.exception("structured tool %s failed", name)
                result = {"ok": False, "tool": name, "error": "the lookup failed; apologise and answer from the other context"}
            span.set("output.value", json.dumps(result, default=str)[:2000])
            span.set("hms.rows", result.get("count"))
        self.calls.append({"name": name, "args": args, "ok": result["ok"], "rows": result.get("count", 0),
                           "error": result.get("error"), "ms": round((time.perf_counter() - began) * 1000), "result": result})
        return result

    # ---- shared pieces
    def _hotels(self):
        query = self.db.query(Hotel).filter(Hotel.deleted_at.is_(None))
        return query.filter(Hotel.id == self.scope_hotel_id) if self.scope_hotel_id else query

    def _ratings(self) -> Dict[uuid.UUID, tuple]:
        """True average rating and review count per hotel, over ALL reviews."""
        rows = (self.db.query(Booking.hotel_id, func.avg(Review.rating), func.count(Review.id))
                .join(Booking, Review.booking_id == Booking.id)
                .filter(Review.deleted_at.is_(None), Booking.deleted_at.is_(None))
                .group_by(Booking.hotel_id).all())
        return {hotel_id: (float(avg), int(n)) for hotel_id, avg, n in rows}

    def _amenity_filter(self, keyword: str):
        """Hotels (or room types) offering an amenity at hotel level or room-type level; same shape as hotel_service."""
        return (self.db.query(Amenity.id).outerjoin(RoomType, Amenity.room_type_id == RoomType.id)
                .filter(Amenity.deleted_at.is_(None), Amenity.name.ilike(_like(keyword), escape="\\"),
                        or_(Amenity.hotel_id == Hotel.id, RoomType.hotel_id == Hotel.id)))

    @staticmethod
    def _page(rows: List[Dict[str, Any]], limit: int) -> Dict[str, Any]:
        return {"count": min(len(rows), limit), "truncated": len(rows) > limit, "rows": rows[:limit]}

    # ---- tool 1
    def _search_hotels(self, args: Dict[str, Any]) -> Dict[str, Any]:
        city, country = _text(args, "city"), _text(args, "country")
        amenity, policy = _text(args, "amenity"), _text(args, "policy_keyword")
        min_rating = _number(args, "min_rating", 1, 5)
        sort_by = _choice(args, "sort_by", ["rating_desc", "rating_asc", "name", "price_asc"], "name")
        limit = _integer(args, "limit", 1, MAX_ROWS, MAX_ROWS)

        query = self._hotels()
        if city:
            query = query.filter(Hotel.city.ilike(_like(city), escape="\\"))
        if country:
            query = query.filter(Hotel.country.ilike(_like(country), escape="\\"))
        if amenity:
            query = query.filter(self._amenity_filter(amenity).exists())
        if policy:
            query = query.filter(self.db.query(Policy.id).filter(
                Policy.hotel_id == Hotel.id, Policy.deleted_at.is_(None),
                or_(Policy.policy_type.ilike(_like(policy), escape="\\"), Policy.description.ilike(_like(policy), escape="\\"))).exists())
        hotels = query.limit(500).all()

        ratings = self._ratings()
        prices = dict(self.db.query(RoomType.hotel_id, func.min(RoomType.base_price))
                      .filter(RoomType.deleted_at.is_(None)).group_by(RoomType.hotel_id).all())
        amenity_rows = (self.db.query(Amenity.hotel_id, Amenity.name)
                        .filter(Amenity.deleted_at.is_(None), Amenity.hotel_id.in_([h.id for h in hotels] or [uuid.uuid4()])).all())
        amenities: Dict[uuid.UUID, List[str]] = {}
        for hotel_id, name in amenity_rows:
            amenities.setdefault(hotel_id, []).append(name)

        rows = []
        for h in hotels:
            avg, n = ratings.get(h.id, (None, 0))
            if min_rating is not None and (avg is None or avg < min_rating):
                continue
            rows.append({"hotel": h.name, "city": h.city, "country": h.country, "average_rating": _num(avg), "review_count": n,
                         "lowest_nightly_price": _num(prices.get(h.id)), "amenities": amenities.get(h.id, [])[:8]})
        keys = {"rating_desc": lambda r: (-(r["average_rating"] or 0), r["hotel"]), "rating_asc": lambda r: (r["average_rating"] or 99, r["hotel"]),
                "price_asc": lambda r: (r["lowest_nightly_price"] or 1e9, r["hotel"]), "name": lambda r: r["hotel"]}
        rows.sort(key=keys[sort_by])
        return self._page(rows, limit)

    # ---- tool 2
    def _search_room_types(self, args: Dict[str, Any]) -> Dict[str, Any]:
        hotel_name, amenity = _text(args, "hotel_name"), _text(args, "amenity")
        low, high = _number(args, "min_price", 0, 1_000_000), _number(args, "max_price", 0, 1_000_000)
        guests = _integer(args, "min_guests", 1, 20)
        sort_by = _choice(args, "sort_by", ["price_asc", "price_desc"], "price_asc")
        limit = _integer(args, "limit", 1, MAX_ROWS, MAX_ROWS)

        query = (self.db.query(RoomType, Hotel).join(Hotel, Hotel.id == RoomType.hotel_id)
                 .filter(RoomType.deleted_at.is_(None), Hotel.deleted_at.is_(None)))
        if self.scope_hotel_id:
            query = query.filter(Hotel.id == self.scope_hotel_id)
        if hotel_name:
            query = query.filter(Hotel.name.ilike(_like(hotel_name), escape="\\"))
        if low is not None:
            query = query.filter(RoomType.base_price >= low)
        if high is not None:
            query = query.filter(RoomType.base_price <= high)
        if guests:
            query = query.filter(RoomType.guests_allowed >= guests)
        if amenity:
            query = query.filter(self.db.query(Amenity.id).filter(
                Amenity.deleted_at.is_(None), Amenity.name.ilike(_like(amenity), escape="\\"),
                or_(Amenity.room_type_id == RoomType.id, Amenity.hotel_id == Hotel.id)).exists())
        order = RoomType.base_price.desc() if sort_by == "price_desc" else RoomType.base_price.asc()
        found = query.order_by(order, Hotel.name, RoomType.name).limit(limit + 1).all()
        rows = [{"hotel": h.name, "room_type": rt.name, "price_per_night": _num(rt.base_price), "sleeps": rt.guests_allowed,
                 "description": (rt.description or "")[:100]} for rt, h in found]
        return self._page(rows, limit)

    # ---- tool 3
    def _check_availability(self, args: Dict[str, Any]) -> Dict[str, Any]:
        checkin, checkout = _date(args, "checkin_date"), _date(args, "checkout_date")
        if checkin < self.today:
            raise ToolError(f"check-in {checkin} is in the past (today is {self.today})")
        if checkout <= checkin:
            raise ToolError("check-out must be after check-in")
        nights = (checkout - checkin).days
        if nights > MAX_STAY_NIGHTS:
            raise ToolError(f"stays are limited to {MAX_STAY_NIGHTS} nights")
        rooms = _integer(args, "rooms", 1, MAX_ROOMS, 1)
        guests = _integer(args, "guests", 1, 20)
        hotel_name, room_name = _text(args, "hotel_name"), _text(args, "room_type_name")

        query = (self.db.query(RoomType, Hotel).join(Hotel, Hotel.id == RoomType.hotel_id)
                 .filter(RoomType.deleted_at.is_(None), Hotel.deleted_at.is_(None)))
        if self.scope_hotel_id:
            query = query.filter(Hotel.id == self.scope_hotel_id)
        if hotel_name:
            query = query.filter(Hotel.name.ilike(_like(hotel_name), escape="\\"))
        if room_name:
            query = query.filter(RoomType.name.ilike(_like(room_name), escape="\\"))
        if guests:
            query = query.filter(RoomType.guests_allowed >= guests)

        rows = []
        for rt, h in query.order_by(Hotel.name, RoomType.base_price).limit(60).all():
            total, free = room_type_availability(self.db, rt.id, checkin, checkout)
            price = float(rt.base_price)
            rows.append({"hotel": h.name, "room_type": rt.name, "sleeps": rt.guests_allowed, "price_per_night": _num(price),
                         "rooms_in_hotel": total, "rooms_available": free, "can_book_requested_rooms": free >= rooms,
                         "estimated_total": _num(price * nights * rooms)})
        rows.sort(key=lambda r: (not r["can_book_requested_rooms"], r["price_per_night"]))
        result = self._page(rows, MAX_ROWS)
        result.update({"checkin_date": str(checkin), "checkout_date": str(checkout), "nights": nights, "rooms_requested": rooms})
        if not rows:
            result["note"] = "no room type matched those filters"
        return result

    # ---- tool 4
    def _catalog_stats(self, args: Dict[str, Any]) -> Dict[str, Any]:
        metric = _choice(args, "metric", ["hotel_count", "room_type_count", "avg_price", "min_price", "max_price", "avg_rating"])
        if metric is None:
            raise ToolError("metric is required")
        group = _choice(args, "group_by", ["city", "country", "hotel", "all"], "all")
        group_column = {"city": Hotel.city, "country": Hotel.country, "hotel": Hotel.name}.get(group)

        if metric == "hotel_count":
            value, count = func.count(func.distinct(Hotel.id)), func.count(func.distinct(Hotel.id))
            query = self.db.query(value, count)
        elif metric == "avg_rating":
            value, count = func.avg(Review.rating), func.count(Review.id)
            query = (self.db.query(value, count).select_from(Review).join(Booking, Review.booking_id == Booking.id)
                     .join(Hotel, Hotel.id == Booking.hotel_id).filter(Review.deleted_at.is_(None), Booking.deleted_at.is_(None)))
        else:
            aggregate = {"room_type_count": func.count(RoomType.id), "avg_price": func.avg(RoomType.base_price),
                         "min_price": func.min(RoomType.base_price), "max_price": func.max(RoomType.base_price)}[metric]
            query = (self.db.query(aggregate, func.count(RoomType.id)).select_from(RoomType)
                     .join(Hotel, Hotel.id == RoomType.hotel_id).filter(RoomType.deleted_at.is_(None)))
        query = query.filter(Hotel.deleted_at.is_(None))
        if self.scope_hotel_id:
            query = query.filter(Hotel.id == self.scope_hotel_id)

        if group_column is not None:
            found = query.add_columns(group_column).group_by(group_column).all()
            rows = [{"group": g, "value": _num(v), "based_on": int(n)} for v, n, g in found]
        else:
            v, n = query.one()
            rows = [{"group": "all", "value": _num(v), "based_on": int(n)}]
        rows.sort(key=lambda r: (-(r["value"] or 0), str(r["group"])))
        result = self._page(rows, MAX_ROWS)
        result.update({"metric": metric, "grouped_by": group})
        return result
