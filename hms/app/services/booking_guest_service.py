from app.utils.validation_utils import validate_string, validate_future_date
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.booking_guest import BookingGuest
from app.schemas.booking_guest import BookingGuestCreate

def create_booking_guest(db: Session, booking_guest: BookingGuestCreate):
    _data_dict = booking_guest.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_booking_guest = BookingGuest(**_data_dict)
    db.add(db_booking_guest)
    db.commit()
    db.refresh(db_booking_guest)
    return db_booking_guest

def get_booking_guests(db: Session, booking_id: uuid.UUID = None):
    query = db.query(BookingGuest)
    if booking_id:
        query = query.filter(BookingGuest.booking_id == booking_id)
    return query.all()

def get_booking_guest_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(BookingGuest).filter(BookingGuest.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingGuest is not present.")
    return item

def update_booking_guest(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(BookingGuest).filter(BookingGuest.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingGuest is not present.")

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

def delete_booking_guest(db: Session, item_id: uuid.UUID):
    item = db.query(BookingGuest).filter(BookingGuest.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This BookingGuest is not present.")
    db.delete(item)
    db.commit()
    return item