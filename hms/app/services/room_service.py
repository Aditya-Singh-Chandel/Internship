from app.utils.validation_utils import validate_string, validate_future_date, validate_room_number_unique_in_hotel
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.room import Room
from app.models.booking import Booking
from app.schemas.room import RoomCreate, BulkRoomCreate


def create_room(db: Session, room: RoomCreate):
    _data_dict = room.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    # Normalize room number
    _data_dict["room_number"] = _data_dict["room_number"].strip()

    # Room number must be unique across all physical rooms in the same hotel (case-insensitive)
    validate_room_number_unique_in_hotel(db, _data_dict["room_type_id"], _data_dict["room_number"])

    db_room = Room(**_data_dict)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room

def create_rooms_bulk(db: Session, bulk_data: BulkRoomCreate):
    from app.models.room_type import RoomType

    room_type = db.query(RoomType).filter(RoomType.id == bulk_data.room_type_id, RoomType.deleted_at.is_(None)).first()
    if not room_type:
        raise HTTPException(status_code=404, detail="The specified room_type does not exist.")

    # 1. Normalize room numbers and check for duplicate room numbers within the incoming payload case-insensitively
    cleaned_numbers = [item.room_number.strip() for item in bulk_data.rooms]
    seen = set()
    intra_dups = []
    for num in cleaned_numbers:
        num_lower = num.lower()
        if num_lower in seen:
            intra_dups.append(num)
        seen.add(num_lower)
    if intra_dups:
        raise HTTPException(status_code=400, detail=f"Duplicate room numbers provided in request batch: {', '.join(set(intra_dups))}.")

    # 2. Case-insensitive database check across all active rooms in the hotel
    lower_numbers = [num.lower() for num in cleaned_numbers]
    conflicts = db.query(Room.room_number).join(RoomType, Room.room_type_id == RoomType.id).filter(
        RoomType.hotel_id == room_type.hotel_id,
        func.lower(func.trim(Room.room_number)).in_(lower_numbers),
        Room.deleted_at.is_(None)
    ).all()
    if conflicts:
        conflict_list = [c[0] for c in conflicts]
        raise HTTPException(status_code=400, detail=f"Room number(s) already exist in this hotel: {', '.join(conflict_list)}.")

    # 3. Create room records with stripped room numbers
    db_rooms = [
        Room(
            room_type_id=bulk_data.room_type_id,
            room_number=item.room_number.strip(),
            floor=item.floor,
            status=item.status.value if hasattr(item.status, "value") else str(item.status)
        )
        for item in bulk_data.rooms
    ]
    db.add_all(db_rooms)
    db.commit()
    for r in db_rooms:
        db.refresh(r)
    return db_rooms

def get_rooms(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(Room)
    query = filter_active(query, Room, query_params)
    query = apply_filters(query, Room, parsed["filters"])
    query = apply_sorting(query, Room, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "rooms", query_params)

def get_room_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Room).filter(Room.id == item_id)
    if not include_deleted:
        query = query.filter(Room.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Room is not present.")
    return item

def update_room(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Room).filter(Room.id == item_id, Room.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Room is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)

    effective_room_type_id = update_data_dict.get("room_type_id", item.room_type_id)
    effective_room_number = update_data_dict.get("room_number", item.room_number)
    if effective_room_number:
        effective_room_number = effective_room_number.strip()
        update_data_dict["room_number"] = effective_room_number

    validate_room_number_unique_in_hotel(db, effective_room_type_id, effective_room_number, exclude_room_id=item.id)

    for key, value in update_data_dict.items():
        if isinstance(value, str):
            value = validate_string(key, value)
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item

def delete_room(db: Session, item_id: uuid.UUID):
    item = db.query(Room).filter(Room.id == item_id, Room.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Room is not present.")

    if item.status == "occupied":
        raise HTTPException(status_code=400, detail="Cannot delete room: physical room is currently occupied.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now

    # Deletion Safeguard: Safely unassign this physical room from any active upcoming booking rooms
    from app.models.booking_room import BookingRoom
    db.query(BookingRoom).filter(
        BookingRoom.room_id == item.id,
        BookingRoom.deleted_at.is_(None),
        BookingRoom.status.notin_(["cancelled", "checked_out"])
    ).update({BookingRoom.room_id: None})

    db.commit()
    db.refresh(item)
    return item

def restore_room(db: Session, item_id: uuid.UUID):
    item = db.query(Room).filter(Room.id == item_id, Room.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Room is not present or not deleted.")

    from app.models.room_type import RoomType
    rt = db.query(RoomType).filter(RoomType.id == item.room_type_id, RoomType.deleted_at.is_(None)).first()
    if not rt:
        raise HTTPException(status_code=400, detail="Cannot restore room: parent room type is deleted.")

    # Re-validate room number uniqueness upon restore
    validate_room_number_unique_in_hotel(db, item.room_type_id, item.room_number, exclude_room_id=item.id)

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item
