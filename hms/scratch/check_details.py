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
from app.models.media import Media

db = session_maker()

print("=== HOTELS AUDIT ===")
hotels = db.query(Hotel).filter(Hotel.deleted_at.is_(None)).all()
for h in hotels:
    rts = db.query(RoomType).filter(RoomType.hotel_id == h.id, RoomType.deleted_at.is_(None)).all()
    rt_ids = [rt.id for rt in rts]
    rms = db.query(Room).filter(Room.room_type_id.in_(rt_ids), Room.deleted_at.is_(None)).all() if rt_ids else []
    pols = db.query(Policy).filter(Policy.hotel_id == h.id, Policy.deleted_at.is_(None)).all()
    bks = db.query(Booking).filter(Booking.hotel_id == h.id, Booking.deleted_at.is_(None)).all()
    bk_ids = [b.id for b in bks]
    rvs = db.query(Review).filter(Review.booking_id.in_(bk_ids), Review.deleted_at.is_(None)).all() if bk_ids else []
    meds = db.query(Media).filter(Media.hotel_id == h.id, Media.deleted_at.is_(None)).all()
    print(f"[{h.name[:35]:35}] Rooms: {len(rms):2} | RTs: {len(rts):2} | Policies: {len(pols):2} | Reviews: {len(rvs):2} | Media: {len(meds):2} | Bookings: {len(bks):2}")

print("\n=== BOOKINGS AUDIT ===")
bks = db.query(Booking).filter(Booking.deleted_at.is_(None)).all()
unassigned_count = 0
assigned_count = 0
missing_guest_count = 0
missing_hotel_count = 0
for b in bks:
    if not b.guest: missing_guest_count += 1
    if not b.hotel: missing_hotel_count += 1
    has_room = False
    for bi in b.booking_items:
        for br in bi.booking_rooms:
            if br.room_id and br.status not in ['cancelled']:
                has_room = True
    if has_room:
        assigned_count += 1
    else:
        unassigned_count += 1
print(f"Total: {len(bks)} | Assigned: {assigned_count} | Unassigned: {unassigned_count} | Missing Guest: {missing_guest_count} | Missing Hotel: {missing_hotel_count}")

print("\n=== REVIEWS AUDIT ===")
reviews = db.query(Review).filter(Review.deleted_at.is_(None)).all()
print(f"Total Reviews: {len(reviews)}")
for r in reviews:
    bk = r.booking
    h = bk.hotel if bk else None
    g = r.guest
    print(f"Review {r.id}: {r.rating}★ by {g.name if g else 'Unknown'} for {h.name if h else 'No Hotel'} (Booking: {bk.id if bk else 'No Booking'})")

print("\n=== POLICIES AUDIT ===")
pols = db.query(Policy).filter(Policy.deleted_at.is_(None)).all()
print(f"Total Policies: {len(pols)}")
cancellation_pols = [p for p in pols if p.policy_type == 'cancellation']
print(f"Cancellation policies: {len(cancellation_pols)}")
for cp in cancellation_pols:
    h = db.query(Hotel).filter(Hotel.id == cp.hotel_id).first() if cp.hotel_id else None
    print(f"  Cancellation policy for {h.name if h else 'GLOBAL'}: {cp.description[:80]}...")

db.close()
