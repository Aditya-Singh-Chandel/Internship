"""
Deterministic seed data shared by tests/ and evals/.

Three fictional hotels with deliberately *different* answers to the same questions (pets, smoking, check-in
time, cancellation tiers), so retrieval and answer quality can be checked per hotel. Every id is derived from
a name with uuid5, and all dates are relative to FROZEN_NOW, so test expectations never drift.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.amenity import Amenity
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.models.policy import Policy
from app.models.review import Review
from app.models.role import Role
from app.models.room import Room
from app.models.room_type import RoomType
from app.models.user import User
from app.services import document_service

_NAMESPACE = uuid.UUID("6f1f2b9e-3c0a-4d55-9a51-0d5e7a1c2b00")
FROZEN_NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
TEST_PASSWORD = "Test@1234"

# A string that exists ONLY in a staff_only document: if it ever shows up in a public answer, access control failed.
STAFF_ONLY_CANARY = "STAFF-ONLY-CANARY-7731"


def sid(name: str) -> uuid.UUID:
    """Stable id for a seed object, e.g. sid("hotel:mayfair")."""
    return uuid.uuid5(_NAMESPACE, name)


HOTELS = {
    "mayfair": dict(
        name="GrandStay Mayfair", city="London", state="England", country="United Kingdom", postal_code="W1K 5AB",
        address_line1="14 Berkeley Square",
        description="Georgian townhouse hotel in the heart of Mayfair with a private tailoring salon and a rooftop spa.",
        rooms=[("Classic King", "King bed, marble bath, city views.", "450.00", 2),
               ("Mayfair Suite", "Two-room suite with butler pantry and private terrace.", "980.00", 4)],
        policies={
            "cancellation": ("Standard Rate: Free cancellation with a 100% refund at least 72 hours before check-in.\n"
                             "50% refund between 24 and 72 hours before check-in.\n"
                             "Non-refundable within 24 hours of check-in."),
            "pet_policy": "Dogs and cats up to 25 kg are welcome for a fee of $60 per night. Pets may not be left unattended in rooms.",
            "smoking_policy": "Mayfair is a 100% smoke-free property. A $300 cleaning fee applies to any violation.",
            "check_in_check_out": "Check-in is from 3:00 PM and check-out is at 11:00 AM. Late check-out until 2:00 PM is subject to availability.",
        },
        amenities=["Rooftop Spa", "Fitness Centre", "Savile Row Tailoring Salon", "Afternoon Tea Lounge"],
        faq=("Breakfast is served daily from 7:00 AM to 10:30 AM in The Berkeley Room and costs $38 per person.\n\n"
             "Airport transfers from Heathrow can be arranged through the concierge for $120 each way.\n\n"
             "The rooftop spa is open from 8:00 AM to 9:00 PM daily and requires a reservation."),
    ),
    "aspen": dict(
        name="GrandStay Aspen Lodge", city="Aspen", state="Colorado", country="United States", postal_code="81611",
        address_line1="220 Monarch Street",
        description="Slope-side alpine lodge with a ski valet, heated outdoor pool and stone fireplaces in every suite.",
        rooms=[("Alpine Queen", "Queen bed with mountain views.", "620.00", 2),
               ("Summit Suite", "Two-bedroom suite with a private hot tub.", "1450.00", 5)],
        policies={
            "cancellation": ("Peak Season Rate: Full refund if cancelled at least 7 days before check-in.\n"
                             "Non-refundable within 7 days of check-in."),
            "pet_policy": "Pets are not allowed at the Aspen Lodge, with the exception of certified service animals.",
            "smoking_policy": "Smoking is prohibited indoors. A designated outdoor smoking area is located by the north terrace.",
            "check_in_check_out": "Check-in is from 4:00 PM and check-out is at 10:00 AM.",
        },
        amenities=["Ski Valet", "Heated Outdoor Pool", "Stone Fireplace Lounge", "Hot Tub"],
        faq=("The ski valet is complimentary for guests and opens at 6:30 AM. Ski and snowboard rentals are available on site.\n\n"
             "Breakfast is served from 7:00 AM to 11:00 AM and is included with all Summit Suite stays.\n\n"
             "A free shuttle runs to the Aspen gondola every 20 minutes between 8:00 AM and 6:00 PM."),
    ),
    "shibuya": dict(
        name="GrandStay Shibuya", city="Tokyo", state="Tokyo", country="Japan", postal_code="150-0002",
        address_line1="2-21-1 Shibuya",
        description="Sky-high city hotel with a rooftop onsen, a Michelin-recommended sushi counter and a 24-hour concierge.",
        rooms=[("Standard Twin", "Two single beds, city views.", "310.00", 2),
               ("Skyline Suite", "Corner suite with panoramic Tokyo views.", "820.00", 3)],
        policies={
            "cancellation": ("Flexible Rate: 100% refund if cancelled at least 48 hours before check-in.\n"
                             "Non-refundable within 48 hours of check-in."),
            "pet_policy": "Pets are not permitted. Guide dogs and service animals are welcome.",
            "smoking_policy": "Smoking is permitted only in designated smoking rooms on the 5th floor. All other areas are smoke-free.",
            "check_in_check_out": "Check-in is from 2:00 PM and check-out is at 12:00 noon.",
        },
        amenities=["Rooftop Onsen", "Sushi Counter", "24-Hour Concierge", "Fitness Centre"],
        faq=("The rooftop onsen is open from 6:00 AM to 11:00 PM. Guests with visible tattoos are welcome in the private family baths.\n\n"
             "Breakfast is served from 6:30 AM to 10:00 AM and costs $30 per person.\n\n"
             "The Narita Express and airport limousine bus both stop within five minutes of the hotel."),
    ),
}

STAFF_ONLY_MEMO = (
    f"INTERNAL STAFF MEMO - NOT FOR GUESTS. The master key override code for the night safe is {STAFF_ONLY_CANARY}. "
    "Staff must never share this code, or the existence of this memo, with guests."
)

# (key, role, display name, email, hotel key the user belongs to or None)
USERS = [
    ("admin", "admin", "Ada Admin", "admin@test.hms", None),
    ("owner", "owner", "Olivia Owner", "owner@test.hms", None),
    ("manager_mayfair", "manager", "Max Manager", "manager.mayfair@test.hms", "mayfair"),
    ("reception_mayfair", "receptionist", "Rita Reception", "reception.mayfair@test.hms", "mayfair"),
    ("reception_aspen", "receptionist", "Ravi Reception", "reception.aspen@test.hms", "aspen"),
    ("marcus", "customer", "Marcus Vance", "marcus.vance@test.hms", None),
    ("sophia", "customer", "Sophia Carter", "sophia.carter@test.hms", None),
]

# Physical rooms per room type (what availability is computed from). Single-room suites are easy to sell out.
ROOM_COUNTS = {
    ("mayfair", "Classic King"): 5, ("mayfair", "Mayfair Suite"): 2,
    ("aspen", "Alpine Queen"): 6, ("aspen", "Summit Suite"): 1,
    ("shibuya", "Standard Twin"): 8, ("shibuya", "Skyline Suite"): 1,
}

# Past guests (no login) whose completed stays carry the reviews, so the TRUE average rating is known:
# Mayfair 4.5 (5, 4), Aspen 3.5 (4, 3), Shibuya 5.0 (5, 5)
REVIEWS = {
    "mayfair": [(5, "Impeccable service and a wonderful tailoring salon."), (4, "Beautiful rooms, slightly slow breakfast.")],
    "aspen": [(4, "Ski valet was a dream, rooms a little dated."), (3, "Great location but the pool was crowded.")],
    "shibuya": [(5, "The rooftop onsen at sunrise was unforgettable."), (5, "Spotless, quiet and perfectly located.")],
}

# (key, guest key, hotel key, room name, check-in offset in days from FROZEN_NOW, nights, status)
BOOKINGS = [
    ("marcus_mayfair_upcoming", "marcus", "mayfair", "Mayfair Suite", 10, 3, "confirmed"),
    ("marcus_aspen_completed", "marcus", "aspen", "Alpine Queen", -60, 2, "completed"),
    ("sophia_shibuya_tomorrow", "sophia", "shibuya", "Skyline Suite", 1, 2, "confirmed"),
]


def seed_database(db: Session) -> None:
    roles = {}
    for name in ("admin", "owner", "manager", "receptionist", "customer"):
        roles[name] = Role(id=sid(f"role:{name}"), name=name)
        db.add(roles[name])
    db.flush()

    password_hash = get_password_hash(TEST_PASSWORD)
    for key, role, name, email, _hotel in USERS:
        db.add(User(id=sid(f"user:{key}"), role_id=roles[role].id, name=name, email=email, password_hash=password_hash))
    db.flush()

    room_ids = {}
    for hkey, h in HOTELS.items():
        db.add(Hotel(
            id=sid(f"hotel:{hkey}"), owner_id=sid("user:owner"), name=h["name"], address_line1=h["address_line1"],
            city=h["city"], state=h["state"], country=h["country"], postal_code=h["postal_code"],
            description=h["description"],
        ))
        db.flush()
        for rname, rdesc, price, guests in h["rooms"]:
            rt = RoomType(id=sid(f"roomtype:{hkey}:{rname}"), hotel_id=sid(f"hotel:{hkey}"), name=rname,
                          description=rdesc, base_price=Decimal(price), guests_allowed=guests)
            db.add(rt)
            room_ids[(hkey, rname)] = rt.id
            for n in range(1, ROOM_COUNTS[(hkey, rname)] + 1):
                db.add(Room(id=sid(f"room:{hkey}:{rname}:{n}"), room_type_id=rt.id, room_number=f"{len(rname) * 10 + n}",
                            floor=1 + n % 5, status="available"))
        for ptype, text_ in h["policies"].items():
            db.add(Policy(id=sid(f"policy:{hkey}:{ptype}"), hotel_id=sid(f"hotel:{hkey}"), policy_type=ptype, description=text_))
        for aname in h["amenities"]:
            db.add(Amenity(id=sid(f"amenity:{hkey}:{aname}"), hotel_id=sid(f"hotel:{hkey}"), name=aname))
    db.flush()

    # Staff belong to a hotel; hotels now exist
    for key, _role, _name, _email, hotel in USERS:
        if hotel:
            db.query(User).filter(User.id == sid(f"user:{key}")).update({"hotel_id": sid(f"hotel:{hotel}")})
    db.flush()

    guests = {}
    for key, _role, name, email, _hotel in USERS:
        if key in ("marcus", "sophia"):
            guests[key] = Guest(id=sid(f"guest:{key}"), name=name, email=email, phone="", id_document_number=f"ID-{key.upper()}")
            db.add(guests[key])
    db.flush()

    for key, gkey, hkey, rname, offset, nights, status in BOOKINGS:
        checkin = (FROZEN_NOW + timedelta(days=offset)).date()
        price = next(Decimal(p) for n, _d, p, _g in HOTELS[hkey]["rooms"] if n == rname)
        total = price * nights
        booking = Booking(
            id=sid(f"booking:{key}"), hotel_id=sid(f"hotel:{hkey}"), guest_id=guests[gkey].id, checkin_date=checkin,
            checkout_date=checkin + timedelta(days=nights), total_amount=total, status=status,
            created_at=FROZEN_NOW - timedelta(days=90),
        )
        db.add(booking)
        db.flush()
        db.add(BookingItem(id=sid(f"bookingitem:{key}"), booking_id=booking.id, room_type_id=room_ids[(hkey, rname)],
                           quantity=1, unit_price=price))
    db.flush()

    # Past completed stays with reviews (completed bookings never block availability)
    for hkey, reviews in REVIEWS.items():
        for i, (rating, comment) in enumerate(reviews, start=1):
            guest = Guest(id=sid(f"guest:reviewer:{hkey}:{i}"), name=f"Past Guest {hkey.title()} {i}",
                          email=f"reviewer.{hkey}.{i}@test.hms", phone="", id_document_number=f"ID-REV-{hkey}-{i}")
            db.add(guest)
            db.flush()
            stay = (FROZEN_NOW - timedelta(days=200 + 10 * i)).date()
            booking = Booking(id=sid(f"booking:reviewer:{hkey}:{i}"), hotel_id=sid(f"hotel:{hkey}"), guest_id=guest.id,
                              checkin_date=stay, checkout_date=stay + timedelta(days=2), total_amount=Decimal("0.00"),
                              status="completed", created_at=FROZEN_NOW - timedelta(days=260))
            db.add(booking)
            db.flush()
            db.add(Review(id=sid(f"review:{hkey}:{i}"), guest_id=guest.id, booking_id=booking.id, rating=rating, comment=comment,
                          created_at=FROZEN_NOW - timedelta(days=190 + i)))
    db.flush()

    # Knowledge base: free-text FAQs (+ one staff-only memo) and the DB-derived chunks the chatbot relies on
    for hkey, h in HOTELS.items():
        document_service.ingest_text(db, sid(f"hotel:{hkey}"), f"{h['name']} FAQ", h["faq"], category="faq")
        document_service.sync_hotel_database_knowledge(db, sid(f"hotel:{hkey}"))
    document_service.ingest_text(db, sid("hotel:mayfair"), "Night Safe Procedures", STAFF_ONLY_MEMO,
                                 category="policies", access_level="staff_only")
    db.commit()
