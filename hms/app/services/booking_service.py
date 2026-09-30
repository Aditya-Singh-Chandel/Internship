from app.utils.validation_utils import (
    validate_string, validate_future_date,
    validate_room_type_belongs_to_hotel, validate_room_belongs_to_room_type,
)
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.booking import Booking
from app.schemas.booking import BookingCreate

def create_booking(db: Session, booking: BookingCreate):
    _data_dict = booking.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    # Cross-reference: room_type must belong to the hotel
    validate_room_type_belongs_to_hotel(db, _data_dict["room_type_id"], _data_dict["hotel_id"])

    # Cross-reference: assigned_room must belong to the room_type (if provided)
    if _data_dict.get("assigned_room_id"):
        validate_room_belongs_to_room_type(db, _data_dict["assigned_room_id"], _data_dict["room_type_id"])

    db_booking = Booking(**_data_dict)
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking

def get_bookings(db: Session, guest_id: str = None, hotel_id: str = None):
    query = db.query(Booking)
    if guest_id:
        query = query.filter(Booking.guest_id == guest_id)
    if hotel_id:
        query = query.filter(Booking.hotel_id == hotel_id)
    return query.all()

def get_booking_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Booking).filter(Booking.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Booking is not present.")
    return item

def update_booking(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Booking).filter(Booking.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Booking is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_data_dict.items():
        if isinstance(value, str):
            value = validate_string(key, value)
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    # After applying updates, resolve the effective values for cross-ref checks
    effective_hotel_id = item.hotel_id
    effective_room_type_id = item.room_type_id
    effective_assigned_room_id = item.assigned_room_id

    # Cross-reference: room_type must belong to the hotel
    validate_room_type_belongs_to_hotel(db, effective_room_type_id, effective_hotel_id)

    # Cross-reference: assigned_room must belong to the room_type (if set)
    if effective_assigned_room_id:
        validate_room_belongs_to_room_type(db, effective_assigned_room_id, effective_room_type_id)

    db.commit()
    db.refresh(item)
    return item

def delete_booking(db: Session, item_id: uuid.UUID):
    item = db.query(Booking).filter(Booking.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Booking is not present.")
    db.delete(item)
    db.commit()
    return item