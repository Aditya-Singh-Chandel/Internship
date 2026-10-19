from datetime import datetime, timezone, date
from decimal import Decimal
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session

from app.models.booking_room import BookingRoom
from app.models.booking_item import BookingItem
from app.models.booking import Booking
from app.models.room import Room
from app.models.room_type import RoomType
from app.models.guest import Guest
from app.schemas.booking_room import BookingRoomCreate, BookingRoomUpdate, BulkRoomAssignmentRequest
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from app.utils.validation_utils import (
    validate_room_belongs_to_room_type,
    validate_assigned_rooms_not_overlapping
)

def create_booking_room(db: Session, booking_room: BookingRoomCreate):
    data = booking_room.model_dump()
    booking_item = db.query(BookingItem).filter(
        BookingItem.id == data["booking_item_id"],
        BookingItem.deleted_at.is_(None)
    ).first()
    if not booking_item:
        raise HTTPException(status_code=404, detail="The specified booking line item does not exist.")

    booking = booking_item.booking
    if not booking or booking.deleted_at is not None:
        raise HTTPException(status_code=404, detail="The master booking does not exist.")

    # Enforce that number of allocated rooms does not exceed booking_item.quantity
    active_rooms_count = db.query(BookingRoom).filter(
        BookingRoom.booking_item_id == booking_item.id,
        BookingRoom.deleted_at.is_(None)
    ).count()
    if active_rooms_count >= booking_item.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add room: line item already has {active_rooms_count} allocated room(s), which meets or exceeds its maximum booked count of {booking_item.quantity}."
        )

    # Default checkin/checkout dates to parent booking if omitted
    if not data.get("checkin_date"):
        data["checkin_date"] = booking.checkin_date
    if not data.get("checkout_date"):
        data["checkout_date"] = booking.checkout_date

    if data["checkin_date"] >= data["checkout_date"]:
        raise HTTPException(status_code=400, detail="checkout_date must be after checkin_date.")

    # Validate resident guest exists
    guest = db.query(Guest).filter(Guest.id == data["guest_id"], Guest.deleted_at.is_(None)).first()
    if not guest:
        raise HTTPException(status_code=404, detail="The specified resident guest does not exist.")

    # Physical room checks (if pre-allocated)
    if data.get("room_id"):
        validate_room_belongs_to_room_type(db, data["room_id"], booking_item.room_type_id)
        validate_assigned_rooms_not_overlapping(db, [data["room_id"]], data["checkin_date"], data["checkout_date"])

    # Auto rate if not set
    if not data.get("room_rate"):
        nights = max(1, (data["checkout_date"] - data["checkin_date"]).days)
        data["room_rate"] = Decimal(booking_item.unit_price) * Decimal(nights)

    db_item = BookingRoom(**data)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def bulk_assign_rooms(db: Session, req: BulkRoomAssignmentRequest):
    """
    Bulk assigns physical rooms to requested booking items in a single transaction.
    Enforces that physical room belongs to room type and requested quantity limit is not exceeded.
    """
    if not req.assignments:
        raise HTTPException(status_code=400, detail="Assignments list cannot be empty.")

    b_item_ids = {a.booking_item_id for a in req.assignments}
    booking_items = db.query(BookingItem).filter(
        BookingItem.id.in_(b_item_ids),
        BookingItem.deleted_at.is_(None)
    ).all()
    items_by_id = {item.id: item for item in booking_items}

    for b_item_id in b_item_ids:
        if b_item_id not in items_by_id:
            raise HTTPException(status_code=404, detail=f"Booking line item '{b_item_id}' not found.")

    if req.booking_id:
        for item in booking_items:
            if str(item.booking_id) != str(req.booking_id):
                raise HTTPException(status_code=400, detail=f"Line item '{item.id}' does not belong to booking '{req.booking_id}'.")

    assigned_counts = {
        item.id: db.query(BookingRoom).filter(
            BookingRoom.booking_item_id == item.id,
            BookingRoom.deleted_at.is_(None)
        ).count()
        for item in booking_items
    }

    created_rooms = []
    assigned_physical_room_ids = []

    for assignment in req.assignments:
        booking_item = items_by_id[assignment.booking_item_id]
        booking = booking_item.booking

        current_count = assigned_counts[booking_item.id]
        if current_count >= booking_item.quantity:
            rt_name = booking_item.room_type.name if booking_item.room_type else "selected room type"
            raise HTTPException(
                status_code=400,
                detail=f"Cannot assign more rooms: line item for '{rt_name}' already has {current_count} of {booking_item.quantity} assigned."
            )

        guest = db.query(Guest).filter(Guest.id == assignment.guest_id, Guest.deleted_at.is_(None)).first()
        if not guest:
            raise HTTPException(status_code=404, detail=f"Resident guest '{assignment.guest_id}' does not exist.")

        validate_room_belongs_to_room_type(db, assignment.room_id, booking_item.room_type_id)

        if assignment.room_id in assigned_physical_room_ids:
            raise HTTPException(status_code=400, detail="Cannot assign the same physical room multiple times in the same batch.")
        validate_assigned_rooms_not_overlapping(db, [assignment.room_id], booking.checkin_date, booking.checkout_date)

        assigned_physical_room_ids.append(assignment.room_id)
        assigned_counts[booking_item.id] = current_count + 1

        br = BookingRoom(
            booking_item_id=booking_item.id,
            room_id=assignment.room_id,
            guest_id=assignment.guest_id,
            checkin_date=booking.checkin_date,
            checkout_date=booking.checkout_date,
            room_rate=booking_item.unit_price,
            status="confirmed"
        )
        created_rooms.append(br)

    db.add_all(created_rooms)
    db.commit()
    for br in created_rooms:
        db.refresh(br)
    return created_rooms

def get_booking_rooms(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    booking_id = query_params.get("booking_id")
    room_type_id = query_params.get("room_type_id")

    parsed = extract_filters(query_params, extra_reserved={"booking_id", "room_type_id"})
    query = db.query(BookingRoom)
    query = filter_active(query, BookingRoom, query_params)

    if booking_id:
        query = query.join(BookingItem, BookingRoom.booking_item_id == BookingItem.id).filter(BookingItem.booking_id == booking_id)
    if room_type_id:
        if not booking_id:
            query = query.join(BookingItem, BookingRoom.booking_item_id == BookingItem.id)
        query = query.filter(BookingItem.room_type_id == room_type_id)

    query = apply_filters(query, BookingRoom, parsed["filters"])
    query = apply_sorting(query, BookingRoom, parsed["sort_by"], parsed["sort_order"])
    return paginate_and_format(query, "booking_rooms", query_params)

def get_booking_room_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(BookingRoom).filter(BookingRoom.id == item_id)
    if not include_deleted:
        query = query.filter(BookingRoom.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingRoom is not present.")
    return item

def update_booking_room(db: Session, item_id: uuid.UUID, update_data: BookingRoomUpdate):
    item = db.query(BookingRoom).filter(BookingRoom.id == item_id, BookingRoom.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingRoom is not present.")

    update_dict = update_data.model_dump(exclude_unset=True)
    if "booking_item_id" in update_dict and update_dict["booking_item_id"] != item.booking_item_id:
        target_item = db.query(BookingItem).filter(BookingItem.id == update_dict["booking_item_id"], BookingItem.deleted_at.is_(None)).first()
        if not target_item:
            raise HTTPException(status_code=404, detail="Target booking item does not exist.")
        target_active_count = db.query(BookingRoom).filter(
            BookingRoom.booking_item_id == target_item.id,
            BookingRoom.deleted_at.is_(None)
        ).count()
        if target_active_count >= target_item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot move room to line item {target_item.id}: target item already has {target_active_count} allocated room(s), meeting its limit of {target_item.quantity}."
            )

    for key, value in update_dict.items():
        setattr(item, key, value)

    if item.checkin_date >= item.checkout_date:
        raise HTTPException(status_code=400, detail="checkout_date must be after checkin_date.")

    if item.room_id:
        validate_room_belongs_to_room_type(db, item.room_id, item.booking_item.room_type_id)
        validate_assigned_rooms_not_overlapping(
            db, [item.room_id], item.checkin_date, item.checkout_date, exclude_booking_room_id=item.id
        )

    db.commit()
    db.refresh(item)
    return item

def check_in_booking_room(db: Session, item_id: uuid.UUID):
    """
    Check-in this specific room and resident guest independently.
    Marks room status as checked_in, sets checked_in_at, and marks parent booking in_house.
    """
    item = db.query(BookingRoom).filter(BookingRoom.id == item_id, BookingRoom.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingRoom is not present.")

    if item.status == "checked_in":
        raise HTTPException(status_code=400, detail="This room is already checked in.")
    if item.status == "checked_out":
        raise HTTPException(status_code=400, detail="This room has already completed its stay.")

    now = datetime.now(timezone.utc)
    item.status = "checked_in"
    item.checked_in_at = now

    # If physical room allocated, update room status
    if item.room_id:
        room = db.query(Room).filter(Room.id == item.room_id).first()
        if room:
            room.status = "occupied"

    # Update parent booking status to 'in_house'
    booking = item.booking_item.booking if item.booking_item else None
    if booking:
        booking.status = "in_house"

    db.commit()
    db.refresh(item)
    return item

def check_out_booking_room(db: Session, item_id: uuid.UUID):
    """
    Check-out this specific room independently.
    Marks room status as checked_out, sets checked_out_at.
    If all rooms in master booking are checked out, marks master booking completed.
    """
    item = db.query(BookingRoom).filter(BookingRoom.id == item_id, BookingRoom.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingRoom is not present.")

    if item.status != "checked_in":
        raise HTTPException(status_code=400, detail="Cannot check out a room that is not currently checked in.")

    now = datetime.now(timezone.utc)
    item.status = "checked_out"
    item.checked_out_at = now

    # If physical room allocated, free it up
    if item.room_id:
        room = db.query(Room).filter(Room.id == item.room_id).first()
        if room:
            room.status = "available"

    # Check if all sibling rooms in this master booking are completed/checked out
    booking = item.booking_item.booking if item.booking_item else None
    if booking:
        sibling_active = [
            r for bi in booking.booking_items if bi.deleted_at is None 
            for r in bi.booking_rooms 
            if r.id != item.id and r.deleted_at is None and r.status in ["confirmed", "checked_in"]
        ]
        if len(sibling_active) == 0:
            booking.status = "completed"

    db.commit()
    db.refresh(item)
    return item

def delete_booking_room(db: Session, item_id: uuid.UUID):
    item = db.query(BookingRoom).filter(BookingRoom.id == item_id, BookingRoom.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingRoom is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now

    # Cascade soft-delete to associated booking guests
    from app.models.booking_guest import BookingGuest
    db.query(BookingGuest).filter(BookingGuest.booking_room_id == item.id, BookingGuest.deleted_at.is_(None)).update({
        BookingGuest.deleted_at: now
    })

    db.commit()
    db.refresh(item)
    return item

def restore_booking_room(db: Session, item_id: uuid.UUID):
    item = db.query(BookingRoom).filter(BookingRoom.id == item_id, BookingRoom.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingRoom is not present or not deleted.")

    from app.models.booking_item import BookingItem
    b_item = db.query(BookingItem).filter(BookingItem.id == item.booking_item_id, BookingItem.deleted_at.is_(None)).first()
    if not b_item:
        raise HTTPException(status_code=400, detail="Cannot restore booking room: parent booking item is deleted.")

    item.deleted_at = None

    from app.models.booking_guest import BookingGuest
    db.query(BookingGuest).filter(BookingGuest.booking_room_id == item.id, BookingGuest.deleted_at.isnot(None)).update({
        BookingGuest.deleted_at: None
    })

    db.commit()
    db.refresh(item)
    return item
