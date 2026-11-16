"""
Rebuilds the database in .env (DATABASE_URL) as a clean, consistent, working demo of the hotel system.

    python -m scripts.seed_demo_db --yes            # DROPS every table, recreates them from the models, fills them
    python -m scripts.seed_demo_db --yes --seed 7   # same, different random booking history

What it creates (content in scripts/demo_content.py):
  * 10 hotels with real coordinates, room types, physically numbered rooms, hotel and room amenities, photos
  * one policy per type per hotel (the types offered by the admin portal), plus uploaded guest-facing and staff-only
    documents, all generated from the same facts so they cannot contradict each other
  * an admin, owners linked to their hotels, a manager and receptionists per hotel, registered customers (each with a
    guest record under the same email) and guests who booked offline
  * about 90 days of past stays and 90 days of future bookings, built from per-room calendars (no double booking).
    Statuses follow from today's date: past stays are completed (checked in and out), guests staying tonight are in
    house (their rooms occupied), and future stays are confirmed; rooms are allocated for the next 14 days. Totals are
    always rate x nights x rooms. Some bookings are cancelled. Reviews follow completed stays only.
  * the AI concierge's knowledge base (documents + synced hotel data, with embeddings)

It then checks its own work and stops with an error if anything is inconsistent. Dates are relative to the day it
runs, so re-running it later gives a fresh, current-looking history. Chat history starts empty.

Demo logins (the frontend's quick-fill buttons): admin@hms.com / Admin@123, owner@hms.com / Owner@123,
manager@hms.com / Manager@123, staff@hms.com / Staff@123, marcus.vance@techcorp.io / Customer@123. Every other account
uses the password of its role (Owner@123, Manager@123, Staff@123, Customer@123). Change them before any public use.
"""
import argparse
import importlib
import os
import pkgutil
import random
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

import app.models as models_pkg  # noqa: E402
from app.core.database import db_class, engine, session_maker  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402

for _m in pkgutil.iter_modules(models_pkg.__path__):  # register every table with the metadata
    importlib.import_module(f"app.models.{_m.name}")

from app.models.amenity import Amenity  # noqa: E402
from app.models.booking import Booking  # noqa: E402
from app.models.booking_guest import BookingGuest  # noqa: E402
from app.models.booking_item import BookingItem  # noqa: E402
from app.models.booking_room import BookingRoom  # noqa: E402
from app.models.guest import Guest  # noqa: E402
from app.models.hotel import Hotel  # noqa: E402
from app.models.media import Media  # noqa: E402
from app.models.policy import Policy  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.room import Room  # noqa: E402
from app.models.room_type import RoomType  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import chat_service, document_service  # noqa: E402
from scripts import demo_content as C  # noqa: E402

PAST_DAYS, FUTURE_DAYS, ALLOCATE_WITHIN_DAYS = 90, 90, 14
CANCEL_RATE, REVIEW_RATE = 0.07, 0.35
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "icloud.com", "hotmail.com"]


# ------------------------------------------------------------------------------------------------ text from facts
def cancellation_text(tiers):
    parts = []
    for i, (hours, pct) in enumerate(tiers):
        notice = f"{hours} hours ({hours // 24} days)" if hours >= 96 else f"{hours} hours"
        refund = "a full refund" if pct == 100 else f"a {pct}% refund"
        if i == 0:
            parts.append(f"Cancellations made at least {notice} before check-in receive {refund}.")
        else:
            parts.append(f"Cancellations made between {hours} and {tiers[i - 1][0]} hours before check-in receive {refund}.")
    parts.append(f"Cancellations made less than {tiers[-1][0]} hours before check-in, and no-shows, are non-refundable.")
    return " ".join(parts)


def policies_for(h):
    pols = {"cancellation": cancellation_text(h["cancellation"]),
            "check_in_check_out": f"Check-in is from {h['checkin']} and check-out is at {h['checkout']} ({h['timezone']}). {h['checkin_extra']}"}
    pols.update(h["policies"])
    return pols


def cancellation_document(h):
    return (f"{h['name'].upper()} - OFFICIAL CANCELLATION & REFUND POLICY\n\n"
            f"Property: {h['name']} ({h['city']}, {h['country']})\n\n"
            f"Refund tiers\n{cancellation_text(h['cancellation'])}\n\n"
            "Notice is counted from the time the cancellation is received until the hotel's standard check-in time on the "
            "day of arrival. Refunds are returned to the original payment card within 5 to 10 business days.\n\n"
            "How to cancel\nCancel online under 'My Reservations' on the GrandStay website, ask the AI concierge, or call "
            f"the front desk on {h['phone']}. Changes of date are treated as a cancellation and a new booking.")


# ------------------------------------------------------------------------------------------------ helpers
def reset_schema():
    url = engine.url
    if (url.database or "").endswith("_test"):
        sys.exit("Refusing to seed a *_test database: the test suite manages that one (conftest.py).")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))  # also drops the pgvector extension where it is installed
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    try:  # put pgvector back if the server has it (Docker image); a server without it (plain Windows Postgres) just skips
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        pass
    engine.dispose()
    db_class.metadata.create_all(engine)


def utc_naive(d: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm))


def id_document(rng, country):
    return f"{country}{rng.randint(10_000_000, 99_999_999)}"


class Calendar:
    """Booked nights per physical room; a stay [checkin, checkout) may not overlap another."""

    def __init__(self):
        self.stays = defaultdict(list)

    def free(self, room_id, a, b):
        return all(b <= s or a >= e for s, e in self.stays[room_id])

    def add(self, room_id, a, b):
        self.stays[room_id].append((a, b))

    def next_busy_end(self, room_id, a, b):
        ends = [e for s, e in self.stays[room_id] if not (b <= s or a >= e)]
        return max(ends) if ends else None


# ------------------------------------------------------------------------------------------------ seeding
def seed(db, rng: random.Random, today: date):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    hashes = {}

    def pw(role):
        if role not in hashes:  # one bcrypt hash per role password (bcrypt is slow on purpose)
            hashes[role] = get_password_hash(C.DEMO_PASSWORDS[role])
        return hashes[role]

    roles = {name: Role(name=name) for name in ("admin", "owner", "manager", "receptionist", "customer")}
    db.add_all(roles.values())
    db.flush()

    def user(name, email, role, phone=None, hotel=None, joined_days_ago=400):
        u = User(name=name, email=email.lower(), password_hash=pw(role), phone=phone, role_id=roles[role].id,
                 hotel_id=hotel.id if hotel else None, created_at=now - timedelta(days=joined_days_ago, hours=rng.randint(0, 23)))
        db.add(u)
        return u

    user(C.ADMIN["name"], C.ADMIN["email"], "admin", C.ADMIN["phone"], joined_days_ago=900)
    owners = {k: user(o["name"], o["email"], "owner", o["phone"], joined_days_ago=rng.randint(600, 900)) for k, o in C.OWNERS.items()}
    db.flush()

    # ---------------- hotels, rooms, amenities, policies, media
    hotels, room_types, rooms = {}, {}, defaultdict(list)
    for h in C.HOTELS:
        hotel = Hotel(name=h["name"], address_line1=h["address_line1"], city=h["city"], state=h["state"], country=h["country"],
                      postal_code=h["postal_code"], latitude=h["latitude"], longitude=h["longitude"], description=h["description"],
                      phone=h["phone"], email=h["email"], owner_id=owners[h["owner"]].id)
        db.add(hotel)
        db.flush()
        hotels[h["key"]] = hotel
        for rt_def in h["room_types"]:
            rt = RoomType(hotel_id=hotel.id, name=rt_def["name"], description=rt_def["description"],
                          base_price=Decimal(rt_def["price"]), guests_allowed=rt_def["guests"])
            db.add(rt)
            db.flush()
            room_types[(h["key"], rt.name)] = rt
            for number in rt_def["rooms"]:
                floor = int(number[:-2]) if rt_def.get("floor_from_number") else rt_def["floor"]
                room = Room(room_type_id=rt.id, room_number=number, floor=floor, status="available")
                db.add(room)
                rooms[h["key"]].append((room, rt))
            for a in rt_def.get("amenities", []):
                db.add(Amenity(hotel_id=hotel.id, room_type_id=rt.id, name=a))
        for a in h["amenities"]:
            db.add(Amenity(hotel_id=hotel.id, name=a))
        for ptype, desc in policies_for(h).items():
            db.add(Policy(hotel_id=hotel.id, policy_type=ptype, description=desc))
        url = "https://images.unsplash.com/{}?auto=format&fit=crop&w=1400&q=80"
        for i, photo in enumerate(h["media"]["hotel"]):
            db.add(Media(hotel_id=hotel.id, image_url=url.format(photo), is_primary=(i == 0)))
        for rt_name, photo in h["media"].items():
            if rt_name != "hotel":
                db.add(Media(hotel_id=hotel.id, room_type_id=room_types[(h["key"], rt_name)].id, image_url=url.format(photo), is_primary=True))
    db.flush()

    # ---------------- staff
    for h in C.HOTELS:
        hotel = hotels[h["key"]]
        m_name, m_email = h["staff"]["manager"]
        user(m_name, m_email, "manager", h["phone"], hotel, joined_days_ago=rng.randint(400, 800))
        for r_name, r_email in h["staff"]["receptionists"]:
            user(r_name, r_email, "receptionist", h["phone"], hotel, joined_days_ago=rng.randint(60, 600))

    # ---------------- customers (account + guest record with the same email) and offline guests
    customers = []
    for name, email, phone, cc in C.CUSTOMERS:
        user(name, email, "customer", phone, joined_days_ago=rng.randint(100, 500))
        g = Guest(name=name, email=email.lower(), phone=phone, id_document_number=id_document(rng, cc),
                  created_at=now - timedelta(days=rng.randint(100, 500)))
        db.add(g)
        customers.append(g)
    walkins = []
    for name, cc in C.WALK_IN_GUESTS:
        email = f"{name.lower().replace(' ', '.').replace(chr(39), '')}@{rng.choice(EMAIL_DOMAINS)}" if rng.random() < 0.7 else None
        g = Guest(name=name, email=email, phone=f"+{rng.randint(1, 99)} {rng.randint(100, 999)} {rng.randint(1000000, 9999999)}",
                  id_document_number=id_document(rng, cc), created_at=now - timedelta(days=rng.randint(10, 200)))
        db.add(g)
        walkins.append(g)
    db.flush()
    demo_customer = customers[0]

    # ---------------- bookings
    cal = Calendar()
    guest_busy = defaultdict(list)
    reviewed_text = defaultdict(set)
    stats = defaultdict(int)
    hotel_by_key = {h["key"]: h for h in C.HOTELS}
    maintenance = set()
    for key in ("alpine", "mirage", "tokyo"):
        room, _ = rng.choice(rooms[key])
        room.status = "maintenance"
        maintenance.add(room.id)

    def guest_free(g, a, b):
        return all(b <= s or a >= e for s, e in guest_busy[g.id])

    domestic = {"USA": "US", "France": "FR", "United Kingdom": "GB", "Japan": "JP"}
    pools = {cc: (firsts, lasts, domains) for cc, firsts, lasts, domains in C.NAME_POOLS}

    def new_guest(hkey, when):
        cc = domestic.get(hotel_by_key[hkey]["country"]) if rng.random() < 0.35 else None
        cc = cc if cc in pools else rng.choice(list(pools))
        firsts, lasts, domains = pools[cc]
        first, last = rng.choice(firsts), rng.choice(lasts)
        handle = unicodedata.normalize("NFKD", f"{first}.{last}").encode("ascii", "ignore").decode().lower().replace(" ", "")
        email = f"{handle}{rng.randint(1, 99)}@{rng.choice(domains)}" if rng.random() < 0.85 else None
        g = Guest(name=f"{first} {last}", email=email, phone=f"+{rng.randint(1, 99)} {rng.randint(100, 999)} {rng.randint(1000000, 9999999)}",
                  id_document_number=id_document(rng, cc), created_at=when)
        db.add(g)
        db.flush()
        walkins.append(g)
        return g

    def pick_guest(hkey, a, b):
        """Most hotel guests stay once; registered customers and some others come back a few times."""
        r = rng.random()
        if r < 0.15:
            options = [g for g in customers if g is not demo_customer and len(guest_busy[g.id]) < 4 and guest_free(g, a, b)]
        elif r < 0.25:
            options = [g for g in walkins if len(guest_busy[g.id]) < 3 and guest_free(g, a, b)]
        else:
            options = []
        if options:
            return rng.choice(options)
        return new_guest(hkey, utc_naive(min(a, today) - timedelta(days=rng.randint(3, 60)), 12))

    companions = defaultdict(list)  # a traveller brings the same partner / children every time

    def companions_of(guest, n, when):
        while len(companions[guest.id]) < n:
            surname = guest.name.split()[-1]
            comp = Guest(name=f"{rng.choice(C.COMPANION_FIRST_NAMES)} {surname}", phone=None, email=None,
                         id_document_number=id_document(rng, guest.id_document_number[:2]), created_at=when)
            db.add(comp)
            db.flush()
            companions[guest.id].append(comp)
        return companions[guest.id][:n]

    def make_booking(hkey, room_list, a, b, guest, status_override=None, review=None, request=None):
        """room_list: [(Room, RoomType)] all for the same dates. Creates booking + items + rooms + companions + review."""
        nights = (b - a).days
        if status_override == "cancelled" or (status_override is None and rng.random() < CANCEL_RATE):
            status = "cancelled"
        elif b <= today:
            status = "completed"
        elif a < today or (a == today and rng.random() < 0.5):
            status = "in_house"
        else:
            status = "confirmed"
        lead = rng.randint(3, 75)
        created = utc_naive(min(a - timedelta(days=lead), today), rng.randint(7, 22), rng.randint(0, 59))
        if created > now:
            created = now - timedelta(hours=rng.randint(1, 48))
        by_type = defaultdict(list)
        for room, rt in room_list:
            by_type[rt.id].append((room, rt))
        total = sum(Decimal(rt.base_price) * nights for _, rt in room_list)
        booking = Booking(hotel_id=hotels[hkey].id, guest_id=guest.id, checkin_date=a, checkout_date=b, total_amount=total,
                          status=status, special_requests=request if request is not None else (rng.choice(C.SPECIAL_REQUESTS) if rng.random() < 0.2 else None),
                          created_at=created)
        db.add(booking)
        db.flush()
        for rt_id, pairs in by_type.items():
            rt = pairs[0][1]
            item = BookingItem(booking_id=booking.id, room_type_id=rt_id, quantity=len(pairs), unit_price=Decimal(rt.base_price), created_at=created)
            db.add(item)
            db.flush()
            for room, _ in pairs:
                allocate = status in ("completed", "in_house") or (status == "confirmed" and (a - today).days <= ALLOCATE_WITHIN_DAYS)
                if status == "cancelled":
                    br_status, room_id = "cancelled", None
                elif status == "completed":
                    br_status, room_id = "checked_out", room.id
                elif status == "in_house":
                    br_status, room_id = "checked_in", room.id
                    room.status = "occupied"
                else:
                    br_status, room_id = ("confirmed", room.id) if allocate else ("assigned", None)
                br = BookingRoom(booking_item_id=item.id, room_id=room_id, guest_id=guest.id, status=br_status, checkin_date=a, checkout_date=b,
                                 room_rate=Decimal(rt.base_price), created_at=created,
                                 checked_in_at=utc_naive(a, rng.randint(14, 21), rng.randint(0, 59)) if br_status in ("checked_in", "checked_out") else None,
                                 checked_out_at=utc_naive(b, rng.randint(8, 11), rng.randint(0, 59)) if br_status == "checked_out" else None)
                db.add(br)
                db.flush()
                if status != "cancelled":
                    cal.add(room.id, a, b)
                # travel companions share the first room (up to its capacity); the same people each time
                if room is pairs[0][0] and rt_id == next(iter(by_type)) and rt.guests_allowed >= 2 and rng.random() < 0.65:
                    for comp in companions_of(guest, rng.randint(1, rt.guests_allowed - 1), created):
                        db.add(BookingGuest(booking_id=booking.id, guest_id=comp.id, booking_room_id=br.id))
        if status != "cancelled":
            guest_busy[guest.id].append((a, b))
        stats[f"booking:{status}"] += 1

        if status == "completed" and b + timedelta(days=1) <= today and (review or rng.random() < REVIEW_RATE):
            rating, comment = review or compose_review(hkey)
            if comment:
                when = utc_naive(min(b + timedelta(days=rng.randint(1, 7)), today - timedelta(days=0)), rng.randint(8, 22))
                db.add(Review(guest_id=guest.id, booking_id=booking.id, rating=rating, comment=comment, created_at=min(when, now - timedelta(hours=1))))
                stats["reviews"] += 1
        return booking

    def compose_review(hkey):
        h = hotel_by_key[hkey]
        for _ in range(30):
            rating = rng.choices([5, 4, 3], weights=[60, 30, 10])[0]
            opener = rng.choice(C.REVIEW_OPENERS[rating])
            h1, h2 = rng.sample(h["review_highlights"], 2)
            gripe = rng.choice(h["review_gripes"])
            if rating == 5:
                comment = f"{opener}. {h1[0].upper()}{h1[1:]}, and {h2}."
            elif rating == 4:
                comment = f"{opener}. {h1[0].upper()}{h1[1:]}; our only small complaint is that {gripe}."
            else:
                comment = f"{opener}. {h1[0].upper()}{h1[1:]}, but {gripe}."
            if comment not in reviewed_text[hkey]:
                reviewed_text[hkey].add(comment)
                return rating, comment
        return 5, None

    def room_of(hkey, rt_name, index=0):
        return [(r, rt) for r, rt in rooms[hkey] if rt.name == rt_name and r.id not in maintenance][index]

    # The demo customer's own history, so "My Reservations" and the concierge have something real to show.
    d = today
    make_booking("tokyo", [room_of("tokyo", "Zen Skyline King")], d - timedelta(days=62), d - timedelta(days=58), demo_customer, "completed",
                 review=(5, "Business trip turned into a retreat. The rooftop onsen at sunrise was unforgettable and the room was whisper-quiet."))
    make_booking("mirage", [room_of("mirage", "Deluxe Coral King Suite")], d - timedelta(days=27), d - timedelta(days=24), demo_customer, "completed",
                 review=(4, "Great pool and a superb spa massage. Cabanas were fully booked on Saturday, so reserve early."))
    make_booking("alpine", [room_of("alpine", "Chalet Mountain View Suite")], d + timedelta(days=10), d + timedelta(days=14), demo_customer, "confirmed",
                 request="Two pairs of skis to be delivered to the valet; arriving on the afternoon flight.")
    make_booking("paris", [room_of("paris", "Eiffel Romance Suite")], d + timedelta(days=41), d + timedelta(days=44), demo_customer, "confirmed",
                 request="Celebrating our wedding anniversary.")
    make_booking("santorini", [room_of("santorini", "Aegean Sunset Villa")], d + timedelta(days=25), d + timedelta(days=29), demo_customer, "cancelled")

    # Everyone else: walk each room's calendar from 90 days ago to 90 days ahead.
    for hkey, room_list in rooms.items():
        for room, rt in room_list:
            day = today - timedelta(days=PAST_DAYS + rng.randint(0, 6))
            while day < today + timedelta(days=FUTURE_DAYS):
                day += timedelta(days=rng.choices([0, 1, 2, 3, 5, 8], weights=[22, 22, 18, 14, 14, 10])[0])
                nights = rng.choices([1, 2, 3, 4, 5, 6, 7], weights=[10, 24, 25, 18, 11, 7, 5])[0]
                a, b = day, day + timedelta(days=nights)
                if room.id in maintenance and b > today - timedelta(days=3):
                    break
                busy_end = cal.next_busy_end(room.id, a, b)
                if busy_end:
                    day = busy_end
                    continue
                days_ahead = (a - today).days
                if days_ahead > 14 and rng.random() > max(0.25, 1 - days_ahead / 110):  # far-future dates are less booked
                    day = b
                    continue
                guest = pick_guest(hkey, a, b)
                stay = [(room, rt)]
                if rng.random() < 0.08:  # a second room for family or friends, same dates
                    others = [(r, t) for r, t in room_list if r.id != room.id and r.id not in maintenance and cal.free(r.id, a, b)]
                    if others:
                        stay.append(rng.choice(others))
                make_booking(hkey, stay, a, b, guest)
                day = b
    db.flush()

    # ---------------- knowledge base: documents, then hotel data
    for h in C.HOTELS:
        hid = hotels[h["key"]].id
        document_service.ingest_text(db, hid, "Official Cancellation & Refund Policy", cancellation_document(h), category="policies")
        for doc in h["documents"]:
            document_service.ingest_text(db, hid, doc["title"], doc["text"], category=doc["category"], access_level=doc["access_level"])
    db.commit()
    for h in C.HOTELS:
        document_service.sync_hotel_database_knowledge(db, hotels[h["key"]].id)
    db.commit()
    return stats


# ------------------------------------------------------------------------------------------------ self-check
def verify(db, today):
    problems = []
    q = lambda sql, **kw: db.execute(text(sql), kw).all()  # noqa: E731

    overlaps = q("""select r.room_number, a.checkin_date, b.checkin_date from booking_rooms a join booking_rooms b
                    on a.room_id = b.room_id and a.id < b.id and a.status <> 'cancelled' and b.status <> 'cancelled'
                    and a.checkin_date < b.checkout_date and b.checkin_date < a.checkout_date join rooms r on r.id = a.room_id""")
    if overlaps:
        problems.append(f"{len(overlaps)} double-booked rooms, e.g. {overlaps[0]}")
    totals = q("""select b.id from bookings b join booking_items i on i.booking_id = b.id group by b.id, b.total_amount, b.checkout_date, b.checkin_date
                  having b.total_amount <> sum(i.unit_price * i.quantity * (b.checkout_date - b.checkin_date))""")
    if totals:
        problems.append(f"{len(totals)} bookings whose total is not rate x nights x rooms")
    stale = q("""select status, count(*) from bookings where
                 (status = 'completed' and checkout_date > :t) or (status = 'in_house' and (checkin_date > :t or checkout_date <= :t))
                 or (status = 'confirmed' and checkin_date < :t) group by status""", t=today)
    if stale:
        problems.append(f"statuses that contradict the dates: {stale}")
    occupied = q("""select r.room_number from rooms r where (r.status = 'occupied') <> exists(
                    select 1 from booking_rooms br where br.room_id = r.id and br.status = 'checked_in')""")
    if occupied:
        problems.append(f"room status out of sync with in-house guests: {occupied[:5]}")
    reviews = q("select count(*) from reviews rv join bookings b on b.id = rv.booking_id where b.status <> 'completed'")
    if reviews[0][0]:
        problems.append(f"{reviews[0][0]} reviews on stays that are not completed")
    dup_pol = q("select hotel_id, policy_type, count(*) from policies group by 1, 2 having count(*) > 1")
    if dup_pol:
        problems.append(f"duplicate policy types: {dup_pol}")
    orphans = q("select u.email from users u join roles r on r.id = u.role_id where r.name = 'customer' and not exists (select 1 from guests g where g.email = u.email)")
    if orphans:
        problems.append(f"customers without a guest record: {orphans}")
    unowned = q("select name from hotels where owner_id is null")
    if unowned:
        problems.append(f"hotels without an owner: {unowned}")

    # The refund engine and check-in parser must read exactly the facts in demo_content.
    for h in C.HOTELS:
        hid = db.execute(text("select id from hotels where name = :n"), {"n": h["name"]}).scalar()
        texts = [r[0] for r in q("select description from policies where hotel_id = :h", h=hid)]
        parsed = chat_service.parse_checkin_time(texts)
        expected = datetime.strptime(h["checkin"], "%I:%M %p").time()
        if parsed != expected:
            problems.append(f"{h['key']}: check-in parsed as {parsed}, expected {expected}")
        cancel = cancellation_text(h["cancellation"])
        for hours, pct in h["cancellation"]:
            got, _ = chat_service.evaluate_dynamic_cancellation_policy(cancel, hours + 1, 100.0)
            if round(got * 100) != pct:
                problems.append(f"{h['key']}: {hours + 1}h notice refunds {got:.0%}, expected {pct}%")
        got, _ = chat_service.evaluate_dynamic_cancellation_policy(cancel, h["cancellation"][-1][0] - 1, 100.0)
        if got != 0:
            problems.append(f"{h['key']}: inside the last window refunds {got:.0%}, expected 0%")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="confirm: every table in DATABASE_URL is dropped and rebuilt")
    parser.add_argument("--seed", type=int, default=2026, help="random seed for the booking history")
    args = parser.parse_args()
    target = engine.url.render_as_string(hide_password=True)
    if not args.yes:
        sys.exit(f"This DROPS and rebuilds every table in {target}. Re-run with --yes to continue.")
    print(f"Rebuilding {target} ...")
    reset_schema()
    today = date.today()
    with session_maker() as db:
        stats = seed(db, random.Random(args.seed), today)
        problems = verify(db, today)
        counts = {t: db.execute(text(f"select count(*) from {t}")).scalar() for t in
                  ["hotels", "room_types", "rooms", "amenities", "policies", "users", "guests", "bookings", "booking_items",
                   "booking_rooms", "booking_guests", "reviews", "media", "hotel_documents", "hotel_document_chunks"]}
    print("rows:", ", ".join(f"{k} {v}" for k, v in counts.items()))
    print("bookings:", ", ".join(f"{k.split(':')[1]} {v}" for k, v in sorted(stats.items()) if k.startswith("booking:")), f"| reviews {stats['reviews']}")
    if problems:
        print("\nCONSISTENCY PROBLEMS:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\nAll consistency checks passed.")
    print("Demo logins: admin@hms.com / Admin@123, owner@hms.com / Owner@123, manager@hms.com / Manager@123, "
          "staff@hms.com / Staff@123, marcus.vance@techcorp.io / Customer@123")


if __name__ == "__main__":
    main()
