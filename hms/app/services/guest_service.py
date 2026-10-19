from app.utils.validation_utils import validate_string, validate_future_date
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.guest import Guest
from app.models.review import Review
from app.schemas.guest import GuestCreate


def create_guest(db: Session, guest: GuestCreate):
    _data_dict = guest.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_guest = Guest(**_data_dict)
    db.add(db_guest)
    db.commit()
    db.refresh(db_guest)
    return db_guest

def get_guests(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(Guest)
    query = filter_active(query, Guest, query_params)
    query = apply_filters(query, Guest, parsed["filters"])
    query = apply_sorting(query, Guest, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "guests", query_params)

def get_guest_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Guest).filter(Guest.id == item_id)
    if not include_deleted:
        query = query.filter(Guest.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Guest is not present.")
    return item

def update_guest(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Guest).filter(Guest.id == item_id, Guest.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Guest is not present.")

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

def delete_guest(db: Session, item_id: uuid.UUID):
    item = db.query(Guest).filter(Guest.id == item_id, Guest.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Guest is not present.")

    # Guard: check active reservations
    from app.models.booking import Booking
    from app.models.booking_room import BookingRoom
    from app.models.booking_guest import BookingGuest

    active_booking = db.query(Booking).filter(
        Booking.guest_id == item.id,
        Booking.deleted_at.is_(None),
        Booking.status.notin_(["cancelled", "completed"])
    ).count()
    active_room = db.query(BookingRoom).filter(
        BookingRoom.guest_id == item.id,
        BookingRoom.deleted_at.is_(None),
        BookingRoom.status.notin_(["cancelled", "checked_out"])
    ).count()
    if active_booking > 0 or active_room > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete guest: guest has active or upcoming reservations."
        )

    now = datetime.now(timezone.utc)
    item.deleted_at = now

    # Cascade soft-delete to reviews created by this guest
    db.query(Review).filter(Review.guest_id == item.id, Review.deleted_at.is_(None)).update({
        Review.deleted_at: now
    })

    # Cascade soft-delete to booking guests
    db.query(BookingGuest).filter(BookingGuest.guest_id == item.id, BookingGuest.deleted_at.is_(None)).update({
        BookingGuest.deleted_at: now
    })

    db.commit()
    db.refresh(item)
    return item

def restore_guest(db: Session, item_id: uuid.UUID):
    item = db.query(Guest).filter(Guest.id == item_id, Guest.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Guest is not present or not deleted.")

    item.deleted_at = None

    db.query(Review).filter(Review.guest_id == item.id, Review.deleted_at.isnot(None)).update({
        Review.deleted_at: None
    })

    from app.models.booking_guest import BookingGuest
    db.query(BookingGuest).filter(BookingGuest.guest_id == item.id, BookingGuest.deleted_at.isnot(None)).update({
        BookingGuest.deleted_at: None
    })

    db.commit()
    db.refresh(item)
    return item
