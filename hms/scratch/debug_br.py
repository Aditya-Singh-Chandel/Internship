import sys, os
sys.path.insert(0, os.path.abspath("."))
import traceback
from app.core.database import session_maker
import app.models.role, app.models.user, app.models.guest, app.models.hotel, app.models.room_type, app.models.room, app.models.policy, app.models.amenity, app.models.media, app.models.booking, app.models.booking_item, app.models.booking_room, app.models.booking_guest, app.models.review, app.models.refresh_token, app.models.document, app.models.chat
from app.models.booking import Booking
from app.models.room import Room
from app.schemas.booking_room import BookingRoomCreate
from app.services.booking_room_service import create_booking_room

db = session_maker()
try:
    bk = db.query(Booking).first()
    rm = db.query(Room).filter(Room.hotel_id == bk.hotel_id).first()
    print("Testing direct call with booking:", bk.id, "and room:", rm.id)
    br = BookingRoomCreate(
        booking_id=bk.id,
        room_id=rm.id,
        guest_id=bk.guest_id
    )
    res = create_booking_room(db, br)
    print("Success:", res.id)
except Exception as e:
    traceback.print_exc()
finally:
    db.close()
