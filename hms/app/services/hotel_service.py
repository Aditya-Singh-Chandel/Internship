from app.utils.validation_utils import validate_string, validate_future_date
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy import func, or_, desc, asc
from sqlalchemy.orm import Session
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.models.room import Room
from app.models.booking import Booking
from app.models.amenity import Amenity
from app.models.policy import Policy
from app.models.review import Review
from app.models.media import Media
from app.schemas.hotel import HotelCreate


def create_hotel(db: Session, hotel: HotelCreate):
    _data_dict = hotel.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_hotel = Hotel(**_data_dict)
    db.add(db_hotel)
    db.commit()
    db.refresh(db_hotel)
    return db_hotel
from app.models.review import Review
def get_hotels(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    amenity = query_params.get("amenity")
    amenity_id = query_params.get("amenity_id")
    policy_type = query_params.get("policy_type")
    policy = query_params.get("policy")
    min_rating = query_params.get("min_rating")

    extra_reserved = {"amenity", "amenity_id", "policy_type", "policy", "min_rating"}
    parsed = extract_filters(query_params, extra_reserved=extra_reserved)

    query = db.query(Hotel)
    query = filter_active(query, Hotel, query_params)

    # Filter 1: Amenity (by name or ID, linked at hotel level or room_type level)
    if amenity:
        amenity_subq = (
            db.query(Amenity.id)
            .outerjoin(RoomType, Amenity.room_type_id == RoomType.id)
            .filter(
                Amenity.deleted_at.is_(None),
                Amenity.name.ilike(f"%{str(amenity).strip()}%"),
                or_(
                    Amenity.hotel_id == Hotel.id,
                    RoomType.hotel_id == Hotel.id
                )
            )
        )
        query = query.filter(amenity_subq.exists())

    if amenity_id:
        amenity_id_subq = (
            db.query(Amenity.id)
            .outerjoin(RoomType, Amenity.room_type_id == RoomType.id)
            .filter(
                Amenity.deleted_at.is_(None),
                Amenity.id == amenity_id,
                or_(
                    Amenity.hotel_id == Hotel.id,
                    RoomType.hotel_id == Hotel.id
                )
            )
        )
        query = query.filter(amenity_id_subq.exists())

    # Filter 2: Policy (by policy_type and/or description)
    if policy_type:
        policy_type_subq = db.query(Policy.id).filter(
            Policy.hotel_id == Hotel.id,
            Policy.deleted_at.is_(None),
            Policy.policy_type.ilike(f"%{str(policy_type).strip()}%")
        )
        query = query.filter(policy_type_subq.exists())

    if policy:
        policy_desc_subq = db.query(Policy.id).filter(
            Policy.hotel_id == Hotel.id,
            Policy.deleted_at.is_(None),
            Policy.description.ilike(f"%{str(policy).strip()}%")
        )
        query = query.filter(policy_desc_subq.exists())

    # Filter 3: Review Rating (calculated across bookings of this hotel)
    avg_rating_subq = (
        db.query(func.avg(Review.rating))
        .select_from(Review)
        .join(Booking, Review.booking_id == Booking.id)
        .filter(
            Booking.hotel_id == Hotel.id,
            Review.deleted_at.is_(None),
            Booking.deleted_at.is_(None)
        )
        .scalar_subquery()
    )

    if min_rating is not None:
        query = query.filter(avg_rating_subq >= float(min_rating))

    # Apply standard column filters
    query = apply_filters(query, Hotel, parsed["filters"])

    # Sorting (support rating sort as well)
    if parsed["sort_by"] == "rating":
        if parsed["sort_order"] == "desc":
            query = query.order_by(desc(avg_rating_subq))
        else:
            query = query.order_by(asc(avg_rating_subq))
    else:
        query = apply_sorting(query, Hotel, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "hotels", query_params)

def get_hotel_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Hotel).filter(Hotel.id == item_id)
    if not include_deleted:
        query = query.filter(Hotel.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Hotel is not present.")
    return item

def update_hotel(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Hotel).filter(Hotel.id == item_id, Hotel.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Hotel is not present.")

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

def delete_hotel(db: Session, item_id: uuid.UUID):
    from app.models.booking import Booking
    from app.models.media import Media

    item = db.query(Hotel).filter(Hotel.id == item_id, Hotel.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Hotel is not present.")

    # Active Booking Safeguard: Block deletion if future or active reservations exist at this property
    active_count = db.query(Booking).filter(
        Booking.hotel_id == item.id,
        Booking.deleted_at.is_(None),
        Booking.status.notin_(["cancelled", "completed"])
    ).count()
    if active_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete hotel: there are {active_count} active or upcoming reservation(s) at this property."
        )

    now = datetime.now(timezone.utc)
    item.deleted_at = now

    # Cascade soft delete to associated room types and rooms, amenities, media
    for rt in db.query(RoomType).filter(RoomType.hotel_id == item.id, RoomType.deleted_at.is_(None)).all():
        rt.deleted_at = now
        db.query(Room).filter(Room.room_type_id == rt.id, Room.deleted_at.is_(None)).update({
            Room.deleted_at: now
        })
        db.query(Amenity).filter(Amenity.room_type_id == rt.id, Amenity.deleted_at.is_(None)).update({
            Amenity.deleted_at: now
        })
        db.query(Media).filter(Media.room_type_id == rt.id, Media.deleted_at.is_(None)).update({
            Media.deleted_at: now
        })

    # Cascade soft delete to hotel amenities & policies & media
    db.query(Amenity).filter(Amenity.hotel_id == item.id, Amenity.deleted_at.is_(None)).update({
        Amenity.deleted_at: now
    })

    db.query(Policy).filter(Policy.hotel_id == item.id, Policy.deleted_at.is_(None)).update({
        Policy.deleted_at: now
    })

    db.query(Media).filter(Media.hotel_id == item.id, Media.deleted_at.is_(None)).update({
        Media.deleted_at: now
    })

    db.commit()
    db.refresh(item)
    return item

def restore_hotel(db: Session, item_id: uuid.UUID):
    item = db.query(Hotel).filter(Hotel.id == item_id, Hotel.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Hotel is not present or not deleted.")

    from app.models.media import Media

    item.deleted_at = None

    # Cascade restore room types, rooms, amenities, policies, media
    for rt in db.query(RoomType).filter(RoomType.hotel_id == item.id, RoomType.deleted_at.isnot(None)).all():
        rt.deleted_at = None
        db.query(Room).filter(Room.room_type_id == rt.id, Room.deleted_at.isnot(None)).update({
            Room.deleted_at: None
        })
        db.query(Amenity).filter(Amenity.room_type_id == rt.id, Amenity.deleted_at.isnot(None)).update({
            Amenity.deleted_at: None
        })
        db.query(Media).filter(Media.room_type_id == rt.id, Media.deleted_at.isnot(None)).update({
            Media.deleted_at: None
        })

    db.query(Amenity).filter(Amenity.hotel_id == item.id, Amenity.deleted_at.isnot(None)).update({
        Amenity.deleted_at: None
    })

    db.query(Policy).filter(Policy.hotel_id == item.id, Policy.deleted_at.isnot(None)).update({
        Policy.deleted_at: None
    })

    db.query(Media).filter(Media.hotel_id == item.id, Media.deleted_at.isnot(None)).update({
        Media.deleted_at: None
    })

    db.commit()
    db.refresh(item)
    return item
