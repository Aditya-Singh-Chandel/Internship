from app.utils.validation_utils import validate_string, validate_future_date
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
import math
from fastapi import HTTPException
import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.room_type import RoomType
from app.models.room import Room
from app.models.booking import Booking
from app.models.amenity import Amenity
from app.schemas.room_type import RoomTypeCreate


def create_room_type(db: Session, room_type: RoomTypeCreate):
    _data_dict = room_type.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_room_type = RoomType(**_data_dict)
    db.add(db_room_type)
    db.commit()
    db.refresh(db_room_type)
    return db_room_type

def get_room_types(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    checkin_date = query_params.get("checkin_date")
    checkout_date = query_params.get("checkout_date")

    if (checkin_date and not checkout_date) or (checkout_date and not checkin_date):
        raise HTTPException(
            status_code=400,
            detail="Both checkin_date and checkout_date must be provided together to filter by availability."
        )

    if checkin_date and checkout_date:
        if checkin_date >= checkout_date:
            raise HTTPException(status_code=400, detail="checkout_date must be after checkin_date.")
        if checkin_date < date.today():
            raise HTTPException(status_code=400, detail="checkin_date cannot be in the past.")

    requested_rooms = int(query_params.get("rooms_count", 1) or 1)
    parsed = extract_filters(query_params, extra_reserved={"checkin_date", "checkout_date", "rooms_count"})

    query = db.query(RoomType)
    query = filter_active(query, RoomType, query_params)
    query = apply_filters(query, RoomType, parsed["filters"])
    query = apply_sorting(query, RoomType, parsed["sort_by"], parsed["sort_order"])

    # Filter room types by real-time available physical capacity considering rooms_count
    if checkin_date and checkout_date:
        items = query.all()
        available_items = []
        for rt in items:
            total_rooms = db.query(Room).filter(
                Room.room_type_id == rt.id,
                Room.deleted_at.is_(None),
                Room.status != "maintenance"
            ).count()

            from app.models.booking import Booking
            from app.models.booking_item import BookingItem
            booked_rooms = db.query(func.coalesce(func.sum(BookingItem.quantity), 0)).join(
                Booking, Booking.id == BookingItem.booking_id
            ).filter(
                BookingItem.room_type_id == rt.id,
                Booking.deleted_at.is_(None),
                Booking.status.notin_(["cancelled", "completed"]),
                BookingItem.deleted_at.is_(None),
                Booking.checkin_date < checkout_date,
                Booking.checkout_date > checkin_date
            ).scalar() or 0

            if total_rooms - booked_rooms >= requested_rooms:
                available_items.append(rt)

        page = max(1, int(query_params.get("page") or 1))
        limit = max(1, int(query_params.get("limit") or 10))
        total = len(available_items)
        total_pages = math.ceil(total / limit) if total > 0 else 0
        paged_items = available_items[(page - 1) * limit : page * limit]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "room_types": paged_items,
        }

    return paginate_and_format(query, "room_types", query_params)

def get_room_type_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(RoomType).filter(RoomType.id == item_id)
    if not include_deleted:
        query = query.filter(RoomType.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This RoomType is not present.")
    return item

def update_room_type(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(RoomType).filter(RoomType.id == item_id, RoomType.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This RoomType is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_data_dict.items():
        if isinstance(value, str):
            value = validate_string(key, value)
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item

def delete_room_type(db: Session, item_id: uuid.UUID):
    item = db.query(RoomType).filter(RoomType.id == item_id, RoomType.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This RoomType is not present.")

    # Active Booking Safeguard: Block deletion if future or active reservations exist
    from app.models.booking_item import BookingItem
    from app.models.booking import Booking
    from app.models.media import Media

    active_count = db.query(BookingItem).join(Booking, BookingItem.booking_id == Booking.id).filter(
        BookingItem.room_type_id == item.id,
        BookingItem.deleted_at.is_(None),
        Booking.deleted_at.is_(None),
        Booking.status.notin_(["cancelled", "completed"])
    ).count()
    if active_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete room category: there are {active_count} active or upcoming reservation(s) associated with it."
        )

    # Also verify no physical rooms of this category are currently occupied
    occupied_count = db.query(Room).filter(
        Room.room_type_id == item.id,
        Room.deleted_at.is_(None),
        Room.status == "occupied"
    ).count()
    if occupied_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete room category: {occupied_count} physical room(s) of this type are currently occupied."
        )

    now = datetime.now(timezone.utc)
    item.deleted_at = now

    # Cascade soft-delete to its rooms
    db.query(Room).filter(Room.room_type_id == item.id, Room.deleted_at.is_(None)).update({
        Room.deleted_at: now
    })

    # Cascade soft-delete to amenities specifically linked to this room type
    db.query(Amenity).filter(Amenity.room_type_id == item.id, Amenity.deleted_at.is_(None)).update({
        Amenity.deleted_at: now
    })

    # Cascade soft-delete to media specifically linked to this room type
    db.query(Media).filter(Media.room_type_id == item.id, Media.deleted_at.is_(None)).update({
        Media.deleted_at: now
    })

    db.commit()
    db.refresh(item)
    return item

def restore_room_type(db: Session, item_id: uuid.UUID):
    item = db.query(RoomType).filter(RoomType.id == item_id, RoomType.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This RoomType is not present or not deleted.")

    from app.models.hotel import Hotel
    from app.models.media import Media

    hotel = db.query(Hotel).filter(Hotel.id == item.hotel_id, Hotel.deleted_at.is_(None)).first()
    if not hotel:
        raise HTTPException(status_code=400, detail="Cannot restore room type: parent hotel is deleted.")

    item.deleted_at = None

    # Cascade restore rooms
    db.query(Room).filter(Room.room_type_id == item.id, Room.deleted_at.isnot(None)).update({
        Room.deleted_at: None
    })

    # Cascade restore amenities
    db.query(Amenity).filter(Amenity.room_type_id == item.id, Amenity.deleted_at.isnot(None)).update({
        Amenity.deleted_at: None
    })

    # Cascade restore media
    db.query(Media).filter(Media.room_type_id == item.id, Media.deleted_at.isnot(None)).update({
        Media.deleted_at: None
    })

    db.commit()
    db.refresh(item)
    return item
