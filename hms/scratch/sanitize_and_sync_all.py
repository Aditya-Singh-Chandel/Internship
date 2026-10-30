import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from app.core.database import session_maker
from app.models.role import Role
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.models.room import Room
from app.models.guest import Guest
from app.models.booking import Booking
from app.models.booking_guest import BookingGuest
from app.models.booking_item import BookingItem
from app.models.booking_room import BookingRoom
from app.models.policy import Policy
from app.models.review import Review

db = session_maker()

print("========================================")
print("1. FIXING CORRUPTED CHARACTERS IN TEXT")
print("========================================")
for rt in db.query(RoomType).all():
    if "Vend" in rt.name and "me" in rt.name:
        rt.name = "Vendôme Executive King"
        print(f"Fixed RoomType name: {rt.name}")
    if rt.description and "\ufffd" in rt.description:
        rt.description = rt.description.replace("\ufffd", "e")

for h in db.query(Hotel).all():
    if h.description and "\ufffd" in h.description:
        h.description = h.description.replace("\ufffd", "e")

for p in db.query(Policy).all():
    if p.description and "\ufffd" in p.description:
        p.description = p.description.replace("\ufffd", "e")

for r in db.query(Review).all():
    if r.comment and "\ufffd" in r.comment:
        r.comment = r.comment.replace("\ufffd", "e")

db.commit()

print("\n========================================")
print("2. SANITIZING GUEST PROFILES")
print("========================================")
sample_phones = [
    "+1 (555) 234-8901", "+1 (555) 345-6712", "+1 (555) 456-7823",
    "+1 (555) 567-8934", "+1 (555) 678-9045", "+33 6 55 50 19 28",
    "+44 20 7946 0912", "+81 90 5555 0142", "+1 (555) 789-0156",
    "+1 (555) 890-1267", "+1 (555) 901-2378", "+1 (555) 123-4589"
]
guests = db.query(Guest).filter(Guest.deleted_at.is_(None)).all()
for idx, g in enumerate(guests):
    dirty = False
    if not g.phone or len(g.phone.strip()) < 5:
        g.phone = sample_phones[idx % len(sample_phones)]
        dirty = True
    if not g.id_document_number or len(g.id_document_number.strip()) < 4:
        country_code = "US"
        if ".fr" in (g.email or ""): country_code = "FR"
        elif ".uk" in (g.email or "") or ".co.uk" in (g.email or ""): country_code = "UK"
        elif ".jp" in (g.email or ""): country_code = "JP"
        elif ".sg" in (g.email or ""): country_code = "SG"
        elif ".ie" in (g.email or ""): country_code = "IE"
        g.id_document_number = f"PASSPORT-{country_code}-{10000 + idx * 37}"
        dirty = True
    if dirty:
        print(f"Sanitized Guest {g.name}: Phone={g.phone}, Doc={g.id_document_number}")

db.commit()

print("\n========================================")
print("3. SANITIZING PHYSICAL ROOM INVENTORY")
print("========================================")
# Ensure each room type in every hotel has 3-4 properly numbered physical rooms
hotels = db.query(Hotel).filter(Hotel.deleted_at.is_(None)).all()
for h in hotels:
    hotel_rts = db.query(RoomType).filter(RoomType.hotel_id == h.id, RoomType.deleted_at.is_(None)).all()
    for rt_idx, rt in enumerate(hotel_rts):
        existing_rooms = db.query(Room).filter(Room.room_type_id == rt.id, Room.deleted_at.is_(None)).all()
        floor_num = rt_idx + 1
        # Give distinct, professional room numbers
        needed = 4 - len(existing_rooms)
        for i in range(max(0, needed)):
            room_num = f"{floor_num * 100 + len(existing_rooms) + i + 1}"
            new_room = Room(
                id=uuid.uuid4(),
                room_type_id=rt.id,
                room_number=room_num,
                floor=floor_num,
                status="available"
            )
            db.add(new_room)
            print(f"Created Physical Room #{room_num} (Floor {floor_num}) for {h.name} -> {rt.name}")

db.commit()

print("\n========================================")
print("4. SANITIZING ALL 56 BOOKINGS & LINE ITEMS")
print("========================================")
bookings = db.query(Booking).filter(Booking.deleted_at.is_(None)).order_by(Booking.checkin_date.desc()).all()
updated_items_count = 0
updated_amounts_count = 0
assigned_rooms_count = 0

for b_idx, b in enumerate(bookings):
    hotel = b.hotel
    if not hotel:
        print(f"Skipping orphan booking {b.id}")
        continue

    hotel_rts = db.query(RoomType).filter(RoomType.hotel_id == hotel.id, RoomType.deleted_at.is_(None)).all()
    if not hotel_rts:
        print(f"Hotel {hotel.name} has no room types!")
        continue

    nights = max(1, (b.checkout_date - b.checkin_date).days)

    # 1. Ensure booking has booking_items
    if not b.booking_items:
        chosen_rt = hotel_rts[b_idx % len(hotel_rts)]
        unit_price = chosen_rt.base_price
        new_item = BookingItem(
            id=uuid.uuid4(),
            booking_id=b.id,
            room_type_id=chosen_rt.id,
            quantity=1,
            unit_price=unit_price
        )
        db.add(new_item)
        db.flush()
        b.booking_items = [new_item]
        updated_items_count += 1

    # 2. Ensure total_amount is accurate
    item = b.booking_items[0]
    rt = item.room_type or db.query(RoomType).filter(RoomType.id == item.room_type_id).first()
    expected_amount = Decimal(nights) * Decimal(item.unit_price or rt.base_price)
    if b.total_amount is None or b.total_amount <= 0:
        b.total_amount = expected_amount
        updated_amounts_count += 1

    # 3. Ensure BookingRoom physical assignment exists
    existing_br = db.query(BookingRoom).filter(
        BookingRoom.booking_item_id == item.id,
        BookingRoom.deleted_at.is_(None)
    ).first()

    if not existing_br:
        # Find physical rooms for this room type
        candidate_rooms = db.query(Room).filter(
            Room.room_type_id == item.room_type_id,
            Room.deleted_at.is_(None)
        ).all()

        if candidate_rooms:
            # Pick room cycling by index
            assigned_room = candidate_rooms[b_idx % len(candidate_rooms)]
            br_status = "checked_in" if b.status == "in_house" else (
                "checked_out" if b.status == "completed" else (
                    "cancelled" if b.status == "cancelled" else "confirmed"
                )
            )
            new_br = BookingRoom(
                id=uuid.uuid4(),
                booking_item_id=item.id,
                room_id=assigned_room.id,
                guest_id=b.guest_id,
                status=br_status,
                checkin_date=b.checkin_date,
                checkout_date=b.checkout_date,
                room_rate=item.unit_price or rt.base_price
            )
            db.add(new_br)
            assigned_rooms_count += 1

            if b.status == "in_house":
                assigned_room.status = "occupied"
            elif b.status in ["completed", "cancelled"]:
                if assigned_room.status == "occupied":
                    assigned_room.status = "available"

    # 4. Ensure BookingGuest link exists
    existing_bg = db.query(BookingGuest).filter(
        BookingGuest.booking_id == b.id,
        BookingGuest.guest_id == b.guest_id,
        BookingGuest.deleted_at.is_(None)
    ).first()
    if not existing_bg:
        new_bg = BookingGuest(
            id=uuid.uuid4(),
            booking_id=b.id,
            guest_id=b.guest_id,
            booking_room_id=new_br.id if 'new_br' in locals() and new_br else None
        )
        db.add(new_bg)


db.commit()
print(f"Sanitized Bookings: Created {updated_items_count} line items, fixed {updated_amounts_count} total amounts, created {assigned_rooms_count} physical room door assignments.")

print("\n========================================")
print("5. ENSURING POLICIES FOR ALL 10 HOTELS")
print("========================================")
standard_policy_templates = [
    {
        "type": "cancellation",
        "desc": "Winter/Peak Season: Cancellations received 72+ hours prior to arrival receive a 100% full refund. Notice between 24 and 72 hours qualifies for a 50% partial refund. Less than 24 hours notice or no-shows are non-refundable. Standard Season: Full refund available up to 48 hours before check-in."
    },
    {
        "type": "check_in_check_out",
        "desc": "Check-in begins at 3:00 PM local time. Early check-in from 11:00 AM is available upon request subject to suite readiness. Check-out is strictly at 11:00 AM. Late check-out until 2:00 PM may be arranged with Front Desk concierge."
    },
    {
        "type": "pool_and_spa",
        "desc": "Private cabanas and infinity pools operate daily from 7:00 AM to 9:00 PM. Towel service and poolside refreshment concierge are provided complimentary. Advance reservation is recommended for weekend cabanas."
    },
    {
        "type": "pet_policy",
        "desc": "Well-behaved dogs under 35 lbs are warmly welcomed with advance notice. A one-time deep cleaning sanitation fee of $120 applies per stay. Custom pet bedding and artisan dog bowls are provided upon check-in."
    },
    {
        "type": "quiet_hours",
        "desc": "To preserve our serene luxury atmosphere, evening quiet hours are observed property-wide from 10:00 PM to 7:00 AM. In-suite dining and ambient music should respect fellow sanctuary residents."
    },
    {
        "type": "parking_valet",
        "desc": "White-glove executive valet parking is available 24 hours daily with in-and-out privileges for $45/night. Electric vehicle high-speed Tesla and universal charging stations are available on site."
    },
    {
        "type": "deposit_security",
        "desc": "A major credit card and government-issued photo ID are required at check-in. An incidental authorization hold of $150 per night is placed upon arrival and released upon room inspection at check-out."
    }
]

created_policies = 0
for h in hotels:
    for pol_tpl in standard_policy_templates:
        existing = db.query(Policy).filter(
            Policy.hotel_id == h.id,
            Policy.policy_type == pol_tpl["type"],
            Policy.deleted_at.is_(None)
        ).first()
        if not existing:
            new_pol = Policy(
                id=uuid.uuid4(),
                hotel_id=h.id,
                policy_type=pol_tpl["type"],
                description=pol_tpl["desc"]
            )
            db.add(new_pol)
            created_policies += 1

db.commit()
print(f"Added {created_policies} missing operational policies across hotels.")

print("\n========================================")
print("6. FINAL AUDIT SUMMARY")
print("========================================")
final_hotels = db.query(Hotel).filter(Hotel.deleted_at.is_(None)).count()
final_rooms = db.query(Room).filter(Room.deleted_at.is_(None)).count()
final_bks = db.query(Booking).filter(Booking.deleted_at.is_(None)).count()
final_items = db.query(BookingItem).filter(BookingItem.deleted_at.is_(None)).count()
final_assigned = db.query(BookingRoom).filter(BookingRoom.deleted_at.is_(None), BookingRoom.room_id.isnot(None)).count()
final_reviews = db.query(Review).filter(Review.deleted_at.is_(None)).count()
final_policies = db.query(Policy).filter(Policy.deleted_at.is_(None)).count()

print(f"[OK] Hotels: {final_hotels}")
print(f"[OK] Physical Rooms: {final_rooms}")
print(f"[OK] Bookings: {final_bks}")
print(f"[OK] Booking Line Items: {final_items}")
print(f"[OK] Physical Door Allocations: {final_assigned}")
print(f"[OK] Verified Guest Reviews: {final_reviews}")
print(f"[OK] Operational Policies: {final_policies}")

db.close()
print("\n>>> SANITIZATION COMPLETED SUCCESSFULLY! <<<")

