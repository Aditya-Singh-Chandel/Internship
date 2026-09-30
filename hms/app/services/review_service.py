from app.utils.validation_utils import (
    validate_string, validate_future_date,
    validate_booking_belongs_to_hotel, validate_booking_belongs_to_guest,
)
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.review import Review
from app.schemas.review import ReviewCreate

def create_review(db: Session, review: ReviewCreate):
    _data_dict = review.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    # Cross-reference: booking must belong to the same hotel
    validate_booking_belongs_to_hotel(db, _data_dict["booking_id"], _data_dict["hotel_id"])

    # Cross-reference: booking must belong to the same guest
    validate_booking_belongs_to_guest(db, _data_dict["booking_id"], _data_dict["guest_id"])

    db_review = Review(**_data_dict)
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

def get_reviews(db: Session, hotel_id: str = None, guest_id: str = None):
    query = db.query(Review)
    if hotel_id:
        query = query.filter(Review.hotel_id == hotel_id)
    if guest_id:
        query = query.filter(Review.guest_id == guest_id)
    return query.all()

def get_review_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Review).filter(Review.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Review is not present.")
    return item

def update_review(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Review).filter(Review.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Review is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_data_dict.items():
        if isinstance(value, str):
            value = validate_string(key, value)
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    # After applying updates, resolve the effective values for cross-ref checks
    effective_hotel_id = item.hotel_id
    effective_guest_id = item.guest_id
    effective_booking_id = item.booking_id

    # Cross-reference: booking must belong to the same hotel
    validate_booking_belongs_to_hotel(db, effective_booking_id, effective_hotel_id)

    # Cross-reference: booking must belong to the same guest
    validate_booking_belongs_to_guest(db, effective_booking_id, effective_guest_id)

    db.commit()
    db.refresh(item)
    return item

def delete_review(db: Session, item_id: uuid.UUID):
    item = db.query(Review).filter(Review.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Review is not present.")
    db.delete(item)
    db.commit()
    return item
