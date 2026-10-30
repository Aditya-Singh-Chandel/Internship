from app.core.database import session_maker
from app.models.role import Role
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.models.room import Room
from app.models.guest import Guest
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.booking_room import BookingRoom
from app.models.booking_guest import BookingGuest
from app.models.policy import Policy
from app.models.review import Review
from app.models.amenity import Amenity
from app.models.media import Media

db = session_maker()

print("=== 1. HOTELS ===")
hotels = db.query(Hotel).filter(Hotel.deleted_at.is_(None)).all()
print(f"Total Hotels: {len(hotels)}")
for h in hotels:
    rts = db.query(RoomType).filter(RoomType.hotel_id == h.id, RoomType.deleted_at.is_(None)).all()
    rt_ids = [rt.id for rt in rts]
    rms = db.query(Room).filter(Room.room_type_id.in_(rt_ids), Room.deleted_at.is_(None)).all() if rt_ids else []
    pols = db.query(Policy).filter(Policy.hotel_id == h.id, Policy.deleted_at.is_(None)).all()
    bks = db.query(Booking).filter(Booking.hotel_id == h.id, Booking.deleted_at.is_(None)).all()
    bk_ids = [b.id for b in bks]
    rvs = db.query(Review).filter(Review.booking_id.in_(bk_ids), Review.deleted_at.is_(None)).all() if bk_ids else []
    meds = db.query(Media).filter(Media.hotel_id == h.id, Media.deleted_at.is_(None)).all()
    print(f"Hotel [{h.id}]: {h.name} | City: {h.city} | Country: {h.country}")
    print(f"   RoomTypes: {len(rts)} | Physical Rooms: {len(rms)} | Policies: {len(pols)} | Reviews: {len(rvs)} | Media: {len(meds)} | Bookings: {len(bks)}")

print("\n=== 2. ROOM TYPES CHECK ===")
rtypes = db.query(RoomType).filter(RoomType.deleted_at.is_(None)).all()
for rt in rtypes:
    hotel_exists = db.query(Hotel).filter(Hotel.id == rt.hotel_id, Hotel.deleted_at.is_(None)).first()
    rms_count = db.query(Room).filter(Room.room_type_id == rt.id, Room.deleted_at.is_(None)).count()
    print(f"RT [{rt.id}]: {rt.name} (${rt.base_price}, max {rt.guests_allowed} guests) -> Hotel: {hotel_exists.name if hotel_exists else 'MISSING/ORPHAN'} | Rooms linked: {rms_count}")

print("\n=== 3. PHYSICAL ROOMS CHECK ===")
rooms = db.query(Room).filter(Room.deleted_at.is_(None)).all()
for r in rooms:
    rt = db.query(RoomType).filter(RoomType.id == r.room_type_id, RoomType.deleted_at.is_(None)).first()
    h = db.query(Hotel).filter(Hotel.id == rt.hotel_id, Hotel.deleted_at.is_(None)).first() if rt else None
    if not h or not rt:
        print(f"⚠️ ORPHAN ROOM [{r.id}]: #{r.room_number} -> Hotel: {h.name if h else 'ORPHAN'}, RT: {rt.name if rt else 'ORPHAN'}")
    else:
        print(f"Room #{r.room_number} (Fl {r.floor}, {r.status}) in {h.name} -> RT: {rt.name}")


print("\n=== 4. GUESTS & USERS ===")
guests = db.query(Guest).filter(Guest.deleted_at.is_(None)).all()
users = db.query(User).filter(User.deleted_at.is_(None)).all()
print(f"Total Guests: {len(guests)}, Total Users: {len(users)}")
for g in guests:
    u = db.query(User).filter(User.email == g.email, User.deleted_at.is_(None)).first()
    b_count = db.query(Booking).filter(Booking.guest_id == g.id, Booking.deleted_at.is_(None)).count()
    print(f"Guest [{g.id}]: {g.name} | Email: {g.email} | Phone: {g.phone} | Doc: {g.id_document_number} | Linked User: {u.email if u else 'NONE'} | Bookings: {b_count}")

print("\n=== 5. BOOKINGS & ASSIGNMENTS ===")
bookings = db.query(Booking).filter(Booking.deleted_at.is_(None)).all()
print(f"Total Bookings: {len(bookings)}")
for b in bookings:
    h = db.query(Hotel).filter(Hotel.id == b.hotel_id, Hotel.deleted_at.is_(None)).first()
    g = db.query(Guest).filter(Guest.id == b.guest_id, Guest.deleted_at.is_(None)).first()
    items = b.booking_items
    print(f"Booking [{b.id[:8] if hasattr(b.id, 'hex') else str(b.id)[:8]}]: Status: {b.status.upper()} | Hotel: {h.name if h else 'ORPHAN'} | Guest: {g.name if g else 'ORPHAN'} | Dates: {b.checkin_date} to {b.checkout_date} | Amount: ${b.total_amount}")
    if not items:
        print(f"   ⚠️ BOOKING HAS NO ITEMS!")
    for it in items:
        rt = it.room_type
        print(f"   Item [{it.id}]: {rt.name if rt else 'ORPHAN RT'} x {it.quantity} @ ${it.unit_price}")
        for br in it.booking_rooms:
            rm = db.query(Room).filter(Room.id == br.room_id).first()
            print(f"      Assigned: Room #{rm.room_number if rm else 'NONE'} (Status: {br.status})")

print("\n=== 6. POLICIES ===")
pols = db.query(Policy).filter(Policy.deleted_at.is_(None)).all()
print(f"Total Policies: {len(pols)}")
for p in pols:
    h = db.query(Hotel).filter(Hotel.id == p.hotel_id).first() if p.hotel_id else None
    print(f"Policy [{p.id}]: {p.policy_type} -> Hotel: {h.name if h else 'GLOBAL'}")

print("\n=== 7. REVIEWS ===")
reviews = db.query(Review).filter(Review.deleted_at.is_(None)).all()
print(f"Total Reviews: {len(reviews)}")
for rv in reviews:
    bk = db.query(Booking).filter(Booking.id == rv.booking_id).first() if rv.booking_id else None
    h = db.query(Hotel).filter(Hotel.id == bk.hotel_id).first() if bk else None
    g = db.query(Guest).filter(Guest.id == rv.guest_id).first() if rv.guest_id else None
    print(f"Review [{rv.id}]: {rv.rating}★ for {h.name if h else 'NONE'} by {g.name if g else 'Unknown Guest'}: '{rv.comment[:60]}...'")


db.close()
