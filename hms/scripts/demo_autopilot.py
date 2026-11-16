"""
Keeps the demo hotel business "alive": does the daily work a hotel's staff and guests would do, for every day since the
last run, so the database never goes stale.

    python -m scripts.demo_autopilot          # catch up now (safe to run any time; a second run the same day adds nothing new)

The app runs it automatically when DEMO_AUTOPILOT=true (at startup, then every DEMO_AUTOPILOT_INTERVAL_HOURS).

Each run, in this order:
  1. departures: guests whose check-out date has passed (or is today, after 11 AM) are checked out and their rooms freed;
  2. arrivals: guests due to arrive (today after 4 PM, or earlier days) get a room if they have none and are checked in;
     about 5% are no-shows (recorded as cancelled, since the app has no separate no-show status);
  3. allocation: arrivals in the next 14 days are given a physical room, as the front desk would;
  4. new business: for each day since the last booking was made, new reservations arrive (about one per three rooms per
     day, 1 to 120 days ahead), plus the odd cancellation of a future stay; capacity is checked per room type and night;
  5. reviews: some guests who checked out leave a review, and the hotel's knowledge base is re-synced.

Statuses follow the app's own lifecycle (booking: confirmed -> in_house -> completed | cancelled; room line: assigned ->
confirmed -> checked_in -> checked_out | cancelled). It never runs against a *_test database.
"""
import logging
import os
import random
import sys
import threading
import time as time_module
import unicodedata
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("demo_autopilot")

ALLOCATE_WITHIN_DAYS = 14
NO_SHOW_RATE = 0.05
REVIEW_RATE = 0.35
NEW_BOOKINGS_PER_ROOM_PER_DAY = 0.33   # ~55-60% occupancy with an average stay of ~3 nights
CANCELS_PER_HOTEL_PER_DAY = 0.15
MAX_LEAD_DAYS = 120
CHECKIN_PROCESS_HOUR = 16              # arrivals of the day are checked in from this local hour
CHECKOUT_PROCESS_HOUR = 11             # departures of the day are checked out from this local hour


def _models():
    from app.models.booking import Booking
    from app.models.booking_item import BookingItem
    from app.models.booking_room import BookingRoom
    from app.models.guest import Guest
    from app.models.hotel import Hotel
    from app.models.review import Review
    from app.models.room import Room
    from app.models.room_type import RoomType
    return Booking, BookingItem, BookingRoom, Guest, Hotel, Review, Room, RoomType


def _overlapping(db, room_id, a, b, exclude_id=None):
    _, _, BookingRoom, *_ = _models()
    q = db.query(BookingRoom).filter(BookingRoom.room_id == room_id, BookingRoom.status != "cancelled", BookingRoom.deleted_at.is_(None),
                                     BookingRoom.checkin_date < b, BookingRoom.checkout_date > a)
    if exclude_id:
        q = q.filter(BookingRoom.id != exclude_id)
    return q.first() is not None


def _free_room(db, room_type_id, a, b, exclude_id=None):
    *_, Room, _ = _models()
    rooms = (db.query(Room).filter(Room.room_type_id == room_type_id, Room.deleted_at.is_(None), Room.status != "maintenance")
             .order_by(Room.room_number).all())
    for room in rooms:
        if not _overlapping(db, room.id, a, b, exclude_id):
            return room
    return None


def _refresh_booking_status(booking):
    lines = [br for item in booking.booking_items for br in item.booking_rooms if br.deleted_at is None]
    live = [br for br in lines if br.status != "cancelled"]
    if not live:
        booking.status = "cancelled"
    elif all(br.status == "checked_out" for br in live):
        booking.status = "completed"
    elif any(br.status in ("checked_in", "checked_out") for br in live):
        booking.status = "in_house"


def _release_room(db, room):
    _, _, BookingRoom, *_ = _models()
    if room and room.status == "occupied":
        still = db.query(BookingRoom).filter(BookingRoom.room_id == room.id, BookingRoom.status == "checked_in").first()
        if not still:
            room.status = "available"


def _cancel(db, booking):
    for item in booking.booking_items:
        for br in item.booking_rooms:
            if br.status in ("assigned", "confirmed"):
                br.status = "cancelled"
                br.room_id = None
    booking.status = "cancelled"


# ------------------------------------------------------------------------------------------------ guest + review helpers
def _new_guest(db, rng, country_hint, when):
    from scripts import demo_content as C
    _, _, _, Guest, *_ = _models()
    pools = {cc: (f, l, d) for cc, f, l, d in C.NAME_POOLS}
    cc = country_hint if country_hint in pools and rng.random() < 0.35 else rng.choice(list(pools))
    firsts, lasts, domains = pools[cc]
    first, last = rng.choice(firsts), rng.choice(lasts)
    handle = unicodedata.normalize("NFKD", f"{first}.{last}").encode("ascii", "ignore").decode().lower().replace(" ", "")
    g = Guest(name=f"{first} {last}", email=f"{handle}{rng.randint(1, 99)}@{rng.choice(domains)}" if rng.random() < 0.85 else None,
              phone=f"+{rng.randint(1, 99)} {rng.randint(100, 999)} {rng.randint(1000000, 9999999)}",
              id_document_number=f"{cc}{rng.randint(10_000_000, 99_999_999)}", created_at=when)
    db.add(g)
    db.flush()
    return g


def _review_text(rng, hotel_def, existing):
    from scripts import demo_content as C
    for _ in range(30):
        rating = rng.choices([5, 4, 3], weights=[60, 30, 10])[0]
        h1, h2 = rng.sample(hotel_def["review_highlights"], 2)
        gripe = rng.choice(hotel_def["review_gripes"])
        opener = rng.choice(C.REVIEW_OPENERS[rating])
        comment = {5: f"{opener}. {h1[0].upper()}{h1[1:]}, and {h2}.",
                   4: f"{opener}. {h1[0].upper()}{h1[1:]}; our only small complaint is that {gripe}.",
                   3: f"{opener}. {h1[0].upper()}{h1[1:]}, but {gripe}."}[rating]
        if comment not in existing:
            existing.add(comment)
            return rating, comment
    return None, None


# ------------------------------------------------------------------------------------------------ the daily work
def catch_up(db, now: datetime = None, seed: int = None) -> dict:
    """Brings bookings, rooms and reviews up to `now` (local time). Idempotent within a day. Returns counts."""
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload
    from app.services import document_service
    from scripts import demo_content as C
    Booking, BookingItem, BookingRoom, Guest, Hotel, Review, Room, RoomType = _models()

    now = now or datetime.now()
    today = now.date()
    rng = random.Random(seed if seed is not None else today.toordinal())
    stats = defaultdict(int)
    completed_now = []

    # 1. departures
    due_out = db.query(BookingRoom).filter(BookingRoom.status == "checked_in", BookingRoom.deleted_at.is_(None)).all()
    for br in due_out:
        if br.checkout_date < today or (br.checkout_date == today and now.hour >= CHECKOUT_PROCESS_HOUR):
            br.status = "checked_out"
            br.checked_out_at = datetime.combine(br.checkout_date, time(rng.randint(8, 10), rng.randint(0, 59)))
            _release_room(db, br.room)
            stats["checked_out"] += 1
    db.flush()

    # 2. arrivals (oldest first, so catch-up of several days stays consistent)
    due_in = (db.query(Booking).options(joinedload(Booking.booking_items).joinedload(BookingItem.booking_rooms))
              .filter(Booking.status == "confirmed", Booking.deleted_at.is_(None), Booking.checkin_date <= today)
              .order_by(Booking.checkin_date).all())
    for booking in due_in:
        if booking.checkin_date == today and now.hour < CHECKIN_PROCESS_HOUR:
            continue
        if rng.random() < NO_SHOW_RATE:
            _cancel(db, booking)
            booking.special_requests = ((booking.special_requests or "") + " [No-show]").strip()
            stats["no_shows"] += 1
            continue
        for item in booking.booking_items:
            for br in item.booking_rooms:
                if br.status not in ("assigned", "confirmed") or br.deleted_at is not None:
                    continue
                if br.room_id is None or _overlapping(db, br.room_id, br.checkin_date, br.checkout_date, br.id):
                    room = _free_room(db, item.room_type_id, br.checkin_date, br.checkout_date, br.id)
                    if room is None:  # fully booked: the guest is moved to a sister hotel ("walked")
                        br.status, br.room_id = "cancelled", None
                        stats["walked"] += 1
                        continue
                    br.room_id = room.id
                    db.flush()
                br.checked_in_at = datetime.combine(br.checkin_date, time(rng.randint(14, 21), rng.randint(0, 59)))
                if br.checkout_date < today or (br.checkout_date == today and now.hour >= CHECKOUT_PROCESS_HOUR):
                    br.status = "checked_out"
                    br.checked_out_at = datetime.combine(br.checkout_date, time(rng.randint(8, 10), rng.randint(0, 59)))
                else:
                    br.status = "checked_in"
                    db.query(Room).filter(Room.id == br.room_id).update({Room.status: "occupied"}, synchronize_session=False)
                stats["checked_in"] += 1
        _refresh_booking_status(booking)
    db.flush()

    # bookings whose last room just checked out become completed
    open_stays = (db.query(Booking).options(joinedload(Booking.booking_items).joinedload(BookingItem.booking_rooms))
                  .filter(Booking.status == "in_house", Booking.deleted_at.is_(None)).all())
    for booking in open_stays:
        _refresh_booking_status(booking)
        if booking.status == "completed":
            completed_now.append(booking)
            stats["completed"] += 1
    db.flush()

    # 3. allocate rooms for the next two weeks
    upcoming = (db.query(BookingRoom).join(BookingItem, BookingItem.id == BookingRoom.booking_item_id)
                .filter(BookingRoom.status == "assigned", BookingRoom.room_id.is_(None), BookingRoom.deleted_at.is_(None),
                        BookingRoom.checkin_date <= today + timedelta(days=ALLOCATE_WITHIN_DAYS)).order_by(BookingRoom.checkin_date).all())
    for br in upcoming:
        room = _free_room(db, br.booking_item.room_type_id, br.checkin_date, br.checkout_date, br.id)
        if room:
            br.room_id, br.status = room.id, "confirmed"
            db.flush()
            stats["allocated"] += 1

    # 4. new business for each day since the last booking was made
    last_made = db.query(func.max(Booking.created_at)).scalar()
    days = min((today - last_made.date()).days, 60) if last_made else 0
    hotels = db.query(Hotel).filter(Hotel.deleted_at.is_(None)).all()
    content = {h["name"]: h for h in C.HOTELS}
    domestic = {"USA": "US", "France": "FR", "United Kingdom": "GB", "Japan": "JP"}
    customers = db.query(Guest).filter(Guest.email.in_([c[1] for c in C.CUSTOMERS[1:]])).all()  # never the demo customer
    for offset in range(days, 0, -1):
        booked_on = today - timedelta(days=offset - 1)
        for hotel in hotels:
            types = db.query(RoomType).filter(RoomType.hotel_id == hotel.id, RoomType.deleted_at.is_(None)).all()
            capacity = {rt.id: db.query(Room).filter(Room.room_type_id == rt.id, Room.deleted_at.is_(None), Room.status != "maintenance").count()
                        for rt in types}
            total_rooms = sum(capacity.values())
            arrivals = sum(rng.random() < NEW_BOOKINGS_PER_ROOM_PER_DAY for _ in range(total_rooms))
            for _ in range(arrivals):
                rt = rng.choice([t for t in types if capacity[t.id]] or [None])
                if rt is None:
                    break
                lead = min(int(rng.expovariate(1 / 30)) + 1, MAX_LEAD_DAYS)
                a = booked_on + timedelta(days=lead)
                b = a + timedelta(days=rng.choices([1, 2, 3, 4, 5, 6, 7], weights=[10, 24, 25, 18, 11, 7, 5])[0])
                if a <= today:
                    continue
                busy = db.query(func.count(BookingRoom.id)).join(BookingItem, BookingItem.id == BookingRoom.booking_item_id).filter(
                    BookingItem.room_type_id == rt.id, BookingRoom.status != "cancelled", BookingRoom.deleted_at.is_(None),
                    BookingRoom.checkin_date < b, BookingRoom.checkout_date > a).scalar()
                if busy >= capacity[rt.id]:  # simple and conservative: any overlapping stay counts against every night
                    stats["turned_away"] += 1
                    continue
                guest = None
                if rng.random() < 0.12 and customers:
                    guest = rng.choice(customers)
                if guest is None:
                    guest = _new_guest(db, rng, domestic.get(hotel.country), datetime.combine(booked_on, time(12)))
                created = datetime.combine(booked_on, time(rng.randint(7, 22), rng.randint(0, 59)))
                created = min(created, now - timedelta(minutes=5))
                nights = (b - a).days
                booking = Booking(hotel_id=hotel.id, guest_id=guest.id, checkin_date=a, checkout_date=b, status="confirmed",
                                  total_amount=Decimal(rt.base_price) * nights, created_at=created,
                                  special_requests=rng.choice(C.SPECIAL_REQUESTS) if rng.random() < 0.2 else None)
                db.add(booking)
                db.flush()
                item = BookingItem(booking_id=booking.id, room_type_id=rt.id, quantity=1, unit_price=Decimal(rt.base_price), created_at=created)
                db.add(item)
                db.flush()
                br = BookingRoom(booking_item_id=item.id, guest_id=guest.id, status="assigned", room_id=None, checkin_date=a,
                                 checkout_date=b, room_rate=Decimal(rt.base_price), created_at=created)
                db.add(br)
                db.flush()
                if (a - today).days <= ALLOCATE_WITHIN_DAYS:
                    room = _free_room(db, rt.id, a, b, br.id)
                    if room:
                        br.room_id, br.status = room.id, "confirmed"
                stats["new_bookings"] += 1
            if rng.random() < CANCELS_PER_HOTEL_PER_DAY:  # a guest cancels a future stay
                future = (db.query(Booking).options(joinedload(Booking.booking_items).joinedload(BookingItem.booking_rooms))
                          .filter(Booking.hotel_id == hotel.id, Booking.status == "confirmed", Booking.checkin_date > today + timedelta(days=2))
                          .order_by(func.random()).first())
                if future and future.guest.email != C.CUSTOMERS[0][1]:
                    _cancel(db, future)
                    stats["cancelled"] += 1
        db.flush()

    # 5. reviews from guests who just left
    resync = set()
    existing = defaultdict(set)
    for booking in completed_now:
        if rng.random() >= REVIEW_RATE or booking.guest.email == C.CUSTOMERS[0][1]:
            continue
        written = datetime.combine(booking.checkout_date + timedelta(days=rng.randint(0, 3)), time(rng.randint(8, 22)))
        if written > now:
            continue
        hotel_def = content.get(booking.hotel.name)
        if not hotel_def:
            continue
        if not existing[booking.hotel_id]:
            existing[booking.hotel_id] = {r[0] for r in db.query(Review.comment).join(Booking, Booking.id == Review.booking_id)
                                          .filter(Booking.hotel_id == booking.hotel_id).all()}
        rating, comment = _review_text(rng, hotel_def, existing[booking.hotel_id])
        if comment:
            db.add(Review(guest_id=booking.guest_id, booking_id=booking.id, rating=rating, comment=comment, created_at=written))
            resync.add(booking.hotel_id)
            stats["reviews"] += 1
    db.commit()
    for hotel_id in resync:  # new reviews change the rating and recent comments the concierge knows about
        document_service.sync_hotel_database_knowledge(db, hotel_id)
    db.commit()
    return dict(stats)


# ------------------------------------------------------------------------------------------------ background runner
def _safe_target():
    from app.core.database import engine
    return not (engine.url.database or "").endswith("_test")


def run_once():
    from app.core.database import session_maker
    if not _safe_target():
        logger.warning("Demo autopilot skipped: it never runs against a *_test database.")
        return {}
    with session_maker() as db:
        stats = catch_up(db)
    logger.info("Demo autopilot: %s", stats or "nothing to do")
    return stats


def start_background(interval_hours: float):
    """Runs the catch-up now and then every `interval_hours` in a daemon thread (the app's startup is not delayed)."""
    def loop():
        while True:
            try:
                run_once()
            except Exception:
                logger.exception("Demo autopilot run failed; will retry at the next interval")
            time_module.sleep(max(0.1, interval_hours) * 3600)

    thread = threading.Thread(target=loop, name="demo-autopilot", daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    import importlib
    import pkgutil
    os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = ""
    import app.models as models_pkg
    for _m in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"app.models.{_m.name}")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run_once())
