from app.utils.validation_utils import validate_string, validate_future_date, validate_booking_capacity
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.booking import Booking
from app.models.booking_guest import BookingGuest
from app.schemas.booking_guest import BookingGuestCreate


def create_booking_guest(db: Session, booking_guest: BookingGuestCreate):
    _data_dict = booking_guest.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    booking_id = _data_dict["booking_id"]
    guest_id = _data_dict["guest_id"]

    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.deleted_at.is_(None)).first()
    if not booking:
        raise HTTPException(status_code=404, detail="The specified booking does not exist.")

    if str(booking.guest_id) == str(guest_id):
        raise HTTPException(status_code=400, detail="This guest is already the primary guest on this booking.")

    existing = db.query(BookingGuest).filter(
        BookingGuest.booking_id == booking_id,
        BookingGuest.guest_id == guest_id,
        BookingGuest.deleted_at.is_(None)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This guest is already registered as a companion on this booking.")

    # Enforce maximum guest capacity for this room category
    validate_booking_capacity(db, booking_id)

    db_booking_guest = BookingGuest(**_data_dict)
    db.add(db_booking_guest)
    db.commit()
    db.refresh(db_booking_guest)
    return db_booking_guest

def get_booking_guests(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(BookingGuest)
    query = filter_active(query, BookingGuest, query_params)
    query = apply_filters(query, BookingGuest, parsed["filters"])
    query = apply_sorting(query, BookingGuest, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "booking_guests", query_params)

def get_booking_guest_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(BookingGuest).filter(BookingGuest.id == item_id)
    if not include_deleted:
        query = query.filter(BookingGuest.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingGuest is not present.")
    return item

def update_booking_guest(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(BookingGuest).filter(BookingGuest.id == item_id, BookingGuest.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingGuest is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)

    effective_booking_id = update_data_dict.get("booking_id", item.booking_id)
    effective_guest_id = update_data_dict.get("guest_id", item.guest_id)

    if "booking_id" in update_data_dict or "guest_id" in update_data_dict:
        booking = db.query(Booking).filter(Booking.id == effective_booking_id, Booking.deleted_at.is_(None)).first()
        if not booking:
            raise HTTPException(status_code=404, detail="The specified booking does not exist.")
        if str(booking.guest_id) == str(effective_guest_id):
            raise HTTPException(status_code=400, detail="This guest is already the primary guest on this booking.")

        existing = db.query(BookingGuest).filter(
            BookingGuest.booking_id == effective_booking_id,
            BookingGuest.guest_id == effective_guest_id,
            BookingGuest.id != item.id,
            BookingGuest.deleted_at.is_(None)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="This guest is already registered as a companion on this booking.")

        if "booking_id" in update_data_dict and update_data_dict["booking_id"] != item.booking_id:
            validate_booking_capacity(db, effective_booking_id)

    for key, value in update_data_dict.items():
        if isinstance(value, str):
            value = validate_string(key, value)
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item

def delete_booking_guest(db: Session, item_id: uuid.UUID):
    item = db.query(BookingGuest).filter(BookingGuest.id == item_id, BookingGuest.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingGuest is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now
    db.commit()
    db.refresh(item)
    return item

def restore_booking_guest(db: Session, item_id: uuid.UUID):
    item = db.query(BookingGuest).filter(BookingGuest.id == item_id, BookingGuest.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingGuest is not present or not deleted.")

    from app.models.booking import Booking
    from app.models.guest import Guest
    booking = db.query(Booking).filter(Booking.id == item.booking_id, Booking.deleted_at.is_(None)).first()
    if not booking:
        raise HTTPException(status_code=400, detail="Cannot restore booking guest: parent booking is deleted.")
    guest = db.query(Guest).filter(Guest.id == item.guest_id, Guest.deleted_at.is_(None)).first()
    if not guest:
        raise HTTPException(status_code=400, detail="Cannot restore booking guest: associated guest is deleted.")

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item