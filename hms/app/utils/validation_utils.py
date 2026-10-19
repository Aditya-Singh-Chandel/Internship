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
    skip_regex = ['email', 'password', 'phone', 'contact_number', 'status', 'description', 'special_requests', 'room_number', 'postal_code', 'id_document_number']
    
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
            
    max_length = 1000 if field_name in ['description', 'special_requests', 'comment'] else 255
    if len(new_value) > max_length:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot exceed {max_length} characters.")
        
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


def validate_rooms_belong_to_room_type(db, room_ids, room_type_id):
    """Ensure all given room_ids exist, are active, and belong to the given room_type_id."""
    if not room_ids:
        return
    from app.models.room import Room
    rooms = db.query(Room).filter(Room.id.in_(room_ids), Room.deleted_at.is_(None)).all()
    found_ids = {str(r.id) for r in rooms}
    for rid in room_ids:
        if str(rid) not in found_ids:
            raise HTTPException(status_code=404, detail=f"The specified physical room {rid} does not exist.")
    for r in rooms:
        if str(r.room_type_id) != str(room_type_id):
            raise HTTPException(
                status_code=400,
                detail=f"Room {r.room_number} does not belong to the specified room_type_id."
            )

def validate_room_belongs_to_room_type(db, room_id, room_type_id):
    """Ensure the given room_id actually belongs to the given room_type_id."""
    if room_id:
        validate_rooms_belong_to_room_type(db, [room_id], room_type_id)

def validate_room_type_availability(db, room_type_id, checkin_date, checkout_date, exclude_booking_id=None, requested_rooms=1, exclude_booking_room_id=None):
    """Ensure there is physical inventory available for the given dates taking booked quantities into account."""
    from app.models.room import Room
    from app.models.booking import Booking
    from app.models.booking_item import BookingItem
    from sqlalchemy import func

    # 1. Total usable physical rooms of this type (exclude deleted and maintenance)
    total_rooms = db.query(Room).filter(
        Room.room_type_id == room_type_id,
        Room.deleted_at.is_(None),
        Room.status != "maintenance"
    ).count()
    if total_rooms == 0:
        raise HTTPException(status_code=400, detail="This room type has no available physical rooms configured.")

    # 2. Count overlapping active rooms requested across BookingItems
    query = db.query(func.coalesce(func.sum(BookingItem.quantity), 0)).join(
        Booking, Booking.id == BookingItem.booking_id
    ).filter(
        BookingItem.room_type_id == room_type_id,
        Booking.deleted_at.is_(None),
        Booking.status.notin_(["cancelled", "completed"]),
        BookingItem.deleted_at.is_(None),
        Booking.checkin_date < checkout_date,
        Booking.checkout_date > checkin_date
    )
    
    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)

    booked_rooms_count = int(query.scalar() or 0)
    available_rooms = total_rooms - booked_rooms_count

    if available_rooms < requested_rooms:
        raise HTTPException(
            status_code=400, 
            detail=f"Not enough rooms available between {checkin_date} and {checkout_date}. Requested {requested_rooms}, but only {max(0, available_rooms)} available."
        )


def validate_hotel_room_availability(db, hotel_id, checkin_date, checkout_date, requested_rooms=1, exclude_booking_id=None):
    """
    Ensure the hotel has enough total physical rooms available across all room types
    for the given dates.
    Calculates total usable physical rooms belonging to the hotel, minus the total
    rooms reserved by overlapping active bookings at this hotel.
    """
    from app.models.hotel import Hotel
    from app.models.room import Room
    from app.models.room_type import RoomType
    from app.models.booking import Booking
    from app.models.booking_item import BookingItem
    from sqlalchemy import func

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at.is_(None)).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="The specified hotel does not exist.")

    # 1. Total usable physical rooms in this hotel (active room types and active rooms, not in maintenance)
    total_hotel_rooms = db.query(Room).join(
        RoomType, Room.room_type_id == RoomType.id
    ).filter(
        RoomType.hotel_id == hotel_id,
        RoomType.deleted_at.is_(None),
        Room.deleted_at.is_(None),
        Room.status != "maintenance"
    ).count()

    if total_hotel_rooms == 0:
        raise HTTPException(
            status_code=400,
            detail="This hotel has no available physical rooms configured."
        )

    # 2. Sum of BookingItem quantity for overlapping active bookings at this hotel
    query = db.query(func.coalesce(func.sum(BookingItem.quantity), 0)).join(
        Booking, Booking.id == BookingItem.booking_id
    ).filter(
        Booking.hotel_id == hotel_id,
        Booking.deleted_at.is_(None),
        Booking.status.notin_(["cancelled"]),
        BookingItem.deleted_at.is_(None),
        Booking.checkin_date < checkout_date,
        Booking.checkout_date > checkin_date
    )
    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)

    currently_reserved = int(query.scalar() or 0)
    available_rooms = total_hotel_rooms - currently_reserved

    if available_rooms < requested_rooms:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Not enough rooms available at this hotel between {checkin_date} and {checkout_date}. "
                f"Requested {requested_rooms} room(s), but only {max(0, available_rooms)} available "
                f"(hotel capacity: {total_hotel_rooms}, currently reserved: {currently_reserved})."
            )
        )


def validate_guest_associated_with_booking(db, guest_id, booking_id):
    """
    Ensure the guest is associated with the specified booking.
    The guest can be:
    - Primary booking booker (Booking.guest_id)
    - Resident guest of a room (BookingRoom.guest_id)
    - Companion guest (BookingGuest.guest_id)
    """
    from app.models.booking import Booking
    from app.models.booking_guest import BookingGuest

    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.deleted_at.is_(None)).first()
    if not booking:
        raise HTTPException(status_code=404, detail="The specified booking does not exist.")

    # Check 1: Primary booker
    if str(booking.guest_id) == str(guest_id):
        return True

    # Check 2: Resident room guest
    if any(str(br.guest_id) == str(guest_id) for bi in booking.booking_items for br in bi.booking_rooms):
        return True

    # Check 3: Companion guest
    bg = db.query(BookingGuest).filter(
        BookingGuest.booking_id == booking_id,
        BookingGuest.guest_id == guest_id,
        BookingGuest.deleted_at.is_(None)
    ).first()
    if bg:
        return True

    raise HTTPException(
        status_code=400,
        detail="The guest is not associated with this booking and cannot submit a review for it."
    )


def validate_assigned_rooms_not_overlapping(db, room_ids, checkin_date, checkout_date, exclude_booking_id=None, exclude_booking_room_id=None):
    """
    Ensure none of the physical rooms in room_ids are already assigned to another
    overlapping active stay in BookingRoom during the requested dates.
    """
    if not room_ids:
        return

    from app.models.booking_room import BookingRoom
    from app.models.booking_item import BookingItem

    query = db.query(BookingRoom).filter(
        BookingRoom.room_id.in_(room_ids),
        BookingRoom.deleted_at.is_(None),
        BookingRoom.status.notin_(["cancelled", "checked_out"]),
        BookingRoom.checkin_date < checkout_date,
        BookingRoom.checkout_date > checkin_date
    )

    if exclude_booking_id:
        query = query.join(BookingItem, BookingRoom.booking_item_id == BookingItem.id).filter(BookingItem.booking_id != exclude_booking_id)
    if exclude_booking_room_id:
        query = query.filter(BookingRoom.id != exclude_booking_room_id)

    conflicting = query.first()
    if conflicting:
        raise HTTPException(
            status_code=400,
            detail=f"Physical room is already assigned to another active booking ({conflicting.checkin_date} to {conflicting.checkout_date})."
        )

def validate_assigned_room_not_overlapping(db, room_id, checkin_date, checkout_date, exclude_booking_id=None, exclude_booking_room_id=None):
    """
    Ensure the specific physical room is not already assigned to another
    overlapping active stay during the requested dates.
    """
    if room_id:
        validate_assigned_rooms_not_overlapping(db, [room_id], checkin_date, checkout_date, exclude_booking_id, exclude_booking_room_id)


def validate_booking_capacity(db, booking_id):
    """
    Ensure adding an additional companion guest does not exceed
    the booking's allowed guest limit (sum of RoomType.guests_allowed across all booked rooms).
    Total guests = 1 (primary booker) + companion guests count.
    """
    from app.models.booking import Booking
    from app.models.booking_guest import BookingGuest
    from app.models.room_type import RoomType

    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.deleted_at.is_(None)).first()
    if not booking:
        raise HTTPException(status_code=404, detail="The specified booking does not exist.")

    total_capacity = 0
    total_booked_rooms = 0
    for item in booking.booking_items:
        if item.deleted_at is None:
            total_booked_rooms += item.quantity
            rt = db.query(RoomType).filter(RoomType.id == item.room_type_id, RoomType.deleted_at.is_(None)).first()
            if rt and rt.guests_allowed:
                total_capacity += rt.guests_allowed * item.quantity

    if total_capacity == 0:
        total_capacity = 2 * (total_booked_rooms or 1)

    current_companion_count = db.query(BookingGuest).filter(
        BookingGuest.booking_id == booking_id,
        BookingGuest.deleted_at.is_(None)
    ).count()

    total_guests = 1 + current_companion_count
    if total_guests >= total_capacity:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add guest: maximum capacity of {total_capacity} guests reached for this booking ({total_booked_rooms} room(s))."
        )


def validate_room_number_unique_in_hotel(db, room_type_id, room_number, exclude_room_id=None):
    """
    Ensure the room_number is unique across all physical rooms in the same hotel (case-insensitive & trimmed).
    """
    from app.models.room import Room
    from app.models.room_type import RoomType
    from sqlalchemy import func

    room_type = db.query(RoomType).filter(RoomType.id == room_type_id, RoomType.deleted_at.is_(None)).first()
    if not room_type:
        raise HTTPException(status_code=404, detail="The specified room_type does not exist.")

    clean_number = room_number.strip() if isinstance(room_number, str) else str(room_number).strip()
    query = db.query(Room).join(RoomType, Room.room_type_id == RoomType.id).filter(
        RoomType.hotel_id == room_type.hotel_id,
        func.lower(func.trim(Room.room_number)) == clean_number.lower(),
        Room.deleted_at.is_(None)
    )

    if exclude_room_id:
        query = query.filter(Room.id != exclude_room_id)

    if query.first():
        raise HTTPException(
            status_code=400,
            detail=f"Room number '{clean_number}' already exists in this hotel."
        )


def validate_media_linkage(db, hotel_id, room_type_id):
    """
    Validate media foreign keys:
    Strict Mutual Exclusivity (XOR):
    Media must be linked to EITHER hotel_id OR room_type_id, but not both and not neither.
    """
    from app.models.hotel import Hotel
    from app.models.room_type import RoomType

    if (hotel_id is None and room_type_id is None) or (hotel_id is not None and room_type_id is not None):
        raise HTTPException(
            status_code=400,
            detail="Media must be linked to EITHER a hotel_id OR a room_type_id, but not both."
        )

    if hotel_id:
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at.is_(None)).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="The specified hotel does not exist.")

    if room_type_id:
        room_type = db.query(RoomType).filter(RoomType.id == room_type_id, RoomType.deleted_at.is_(None)).first()
        if not room_type:
            raise HTTPException(status_code=404, detail="The specified room_type does not exist.")


def validate_amenity_linkage(db, hotel_id, room_type_id):
    """
    Validate amenity foreign keys:
    1. If hotel_id is provided, verify hotel exists and is active.
    2. If room_type_id is provided, verify room_type exists and is active.
    3. If BOTH are provided, verify they link to the same hotel.
    """
    from app.models.hotel import Hotel
    from app.models.room_type import RoomType

    hotel = None
    if hotel_id:
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at.is_(None)).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="The specified hotel does not exist.")

    room_type = None
    if room_type_id:
        room_type = db.query(RoomType).filter(RoomType.id == room_type_id, RoomType.deleted_at.is_(None)).first()
        if not room_type:
            raise HTTPException(status_code=404, detail="The specified room_type does not exist.")

    if hotel_id and room_type_id:
        if str(room_type.hotel_id) != str(hotel_id):
            raise HTTPException(
                status_code=400,
                detail="The specified room_type does not belong to the specified hotel."
            )


