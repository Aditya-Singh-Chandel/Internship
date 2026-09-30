import re
from datetime import date
from fastapi import HTTPException

def validate_string(field_name: str, value: str) -> str | None:
    """
    Utility function to dynamically validate and format string inputs.
    - Strips leading, trailing, and duplicate spaces.
    - Prevents empty strings for required inputs.
    - Prevents numeric-only or special-character-only inputs for names/titles.
    - Bypasses strict regex for fields like emails, passwords, and descriptions.
    """
    # Exclude strict regex validation for specific fields
    skip_regex = ['email', 'password', 'phone', 'contact_number', 'status', 'description', 'special_requests', 'floor', 'room_number']
    
    new_value = " ".join(value.split())
    
    # Allow empty descriptions/requests if they are cleared out, but enforce for names
    if not new_value:
        if field_name in ['description', 'special_requests']:
            return None
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty.")
        
    if field_name not in skip_regex:
        if re.fullmatch(r'[\d\s]+', new_value):
            raise HTTPException(status_code=400, detail=f"{field_name} cannot consist solely of numbers.")
        if not re.search(r'[a-zA-Z0-9\U00010000-\U0010ffff\u2600-\u27BF]', new_value):
            raise HTTPException(status_code=400, detail=f"{field_name} cannot consist solely of special characters.")
            
    if len(new_value) > 255:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot exceed 255 characters.")
        
    return new_value

def validate_future_date(field_name: str, value: date) -> date:
    """
    Utility function to ensure a submitted date (e.g., checkin_date)
    is not set in the past.
    """
    if value < date.today():
        raise HTTPException(status_code=400, detail=f"{field_name} must be a date in the future.")
    return value


# ---------------------------------------------------------------------------
# Cross-reference integrity validators
# ---------------------------------------------------------------------------

def validate_room_type_belongs_to_hotel(db, room_type_id, hotel_id):
    """Ensure the given room_type_id actually belongs to the given hotel_id."""
    from app.models.room_type import RoomType

    room_type = db.query(RoomType).filter(RoomType.id == room_type_id).first()
    if not room_type:
        raise HTTPException(status_code=404, detail="The specified room type does not exist.")
    if str(room_type.hotel_id) != str(hotel_id):
        raise HTTPException(
            status_code=400,
            detail="room_type_id does not belong to the specified hotel_id."
        )


def validate_room_belongs_to_room_type(db, room_id, room_type_id):
    """Ensure the given room_id actually belongs to the given room_type_id."""
    from app.models.room import Room

    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="The specified room does not exist.")
    if str(room.room_type_id) != str(room_type_id):
        raise HTTPException(
            status_code=400,
            detail="assigned_room_id does not belong to the specified room_type_id."
        )


def validate_booking_belongs_to_hotel(db, booking_id, hotel_id):
    """Ensure the given booking_id references a booking for the given hotel_id."""
    from app.models.booking import Booking

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="The specified booking does not exist.")
    if str(booking.hotel_id) != str(hotel_id):
        raise HTTPException(
            status_code=400,
            detail="booking_id does not belong to the specified hotel_id."
        )


def validate_booking_belongs_to_guest(db, booking_id, guest_id):
    """Ensure the given booking_id references a booking for the given guest_id."""
    from app.models.booking import Booking

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="The specified booking does not exist.")
    if str(booking.guest_id) != str(guest_id):
        raise HTTPException(
            status_code=400,
            detail="booking_id does not belong to the specified guest_id."
        )
