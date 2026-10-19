from app.utils.validation_utils import (
    validate_string, validate_future_date, validate_guest_associated_with_booking
)
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.review import Review
from app.models.booking import Booking
from app.schemas.review import ReviewCreate


def create_review(db: Session, review: ReviewCreate):
    _data_dict = review.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    booking_id = _data_dict["booking_id"]
    guest_id = _data_dict["guest_id"]

    # 1. Verification: Guest must be associated with the booking
    validate_guest_associated_with_booking(db, guest_id, booking_id)

    # 2. Lifecycle check: Guest cannot review before stay has commenced
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.deleted_at.is_(None)).first()
    if booking and date.today() < booking.checkin_date:
        raise HTTPException(status_code=400, detail="Reviews cannot be submitted prior to the booking check-in date.")

    # 3. Duplicate prevention: Exactly one review per guest per booking
    existing_review = db.query(Review).filter(
        Review.booking_id == booking_id,
        Review.guest_id == guest_id,
        Review.deleted_at.is_(None)
    ).first()
    if existing_review:
        raise HTTPException(status_code=400, detail="Guest has already submitted a review for this booking.")

    db_review = Review(**_data_dict)
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

def get_reviews(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(Review)
    query = filter_active(query, Review, query_params)
    query = apply_filters(query, Review, parsed["filters"])
    query = apply_sorting(query, Review, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "reviews", query_params)

def get_review_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Review).filter(Review.id == item_id)
    if not include_deleted:
        query = query.filter(Review.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Review is not present.")
    return item

def update_review(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Review).filter(Review.id == item_id, Review.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Review is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)

    # If updating guest_id or booking_id, verify the association and uniqueness
    effective_guest_id = update_data_dict.get("guest_id", item.guest_id)
    effective_booking_id = update_data_dict.get("booking_id", item.booking_id)
    validate_guest_associated_with_booking(db, effective_guest_id, effective_booking_id)

    if "guest_id" in update_data_dict or "booking_id" in update_data_dict:
        booking = db.query(Booking).filter(Booking.id == effective_booking_id, Booking.deleted_at.is_(None)).first()
        if booking and date.today() < booking.checkin_date:
            raise HTTPException(status_code=400, detail="Reviews cannot be submitted prior to the booking check-in date.")

        existing_review = db.query(Review).filter(
            Review.booking_id == effective_booking_id,
            Review.guest_id == effective_guest_id,
            Review.id != item.id,
            Review.deleted_at.is_(None)
        ).first()
        if existing_review:
            raise HTTPException(status_code=400, detail="Guest has already submitted a review for this booking.")

    for key, value in update_data_dict.items():
        if isinstance(value, str):
            value = validate_string(key, value)
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item

def delete_review(db: Session, item_id: uuid.UUID):
    item = db.query(Review).filter(Review.id == item_id, Review.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Review is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now
    db.commit()
    db.refresh(item)
    return item

def restore_review(db: Session, item_id: uuid.UUID):
    item = db.query(Review).filter(Review.id == item_id, Review.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Review is not present or not deleted.")

    from app.models.guest import Guest
    from app.models.booking import Booking

    guest = db.query(Guest).filter(Guest.id == item.guest_id, Guest.deleted_at.is_(None)).first()
    if not guest:
        raise HTTPException(status_code=400, detail="Cannot restore review: associated guest is deleted.")

    booking = db.query(Booking).filter(Booking.id == item.booking_id, Booking.deleted_at.is_(None)).first()
    if not booking:
        raise HTTPException(status_code=400, detail="Cannot restore review: associated booking is deleted.")

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item
