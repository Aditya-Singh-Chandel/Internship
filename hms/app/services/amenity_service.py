from app.utils.validation_utils import (
    validate_string, validate_future_date,
    validate_room_type_belongs_to_hotel,
)
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.amenity import Amenity
from app.schemas.amenity import AmenityCreate

def create_amenity(db: Session, amenity: AmenityCreate):
    _data_dict = amenity.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    # Cross-reference: if both hotel_id and room_type_id are set, room_type must belong to the hotel
    if _data_dict.get("hotel_id") and _data_dict.get("room_type_id"):
        validate_room_type_belongs_to_hotel(db, _data_dict["room_type_id"], _data_dict["hotel_id"])

    db_amenity = Amenity(**_data_dict)
    db.add(db_amenity)
    db.commit()
    db.refresh(db_amenity)
    return db_amenity

def get_amenities(db: Session, hotel_id: str = None, room_type_id: str = None):
    query = db.query(Amenity)
    if hotel_id:
        query = query.filter(Amenity.hotel_id == hotel_id)
    if room_type_id:
        query = query.filter(Amenity.room_type_id == room_type_id)
    return query.all()

def get_amenity_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Amenity).filter(Amenity.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Amenity is not present.")
    return item

def update_amenity(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Amenity).filter(Amenity.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Amenity is not present.")

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

    # Cross-reference: if both are set, room_type must belong to the hotel
    if effective_hotel_id and effective_room_type_id:
        validate_room_type_belongs_to_hotel(db, effective_room_type_id, effective_hotel_id)

    db.commit()
    db.refresh(item)
    return item

def delete_amenity(db: Session, item_id: uuid.UUID):
    item = db.query(Amenity).filter(Amenity.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Amenity is not present.")
    db.delete(item)
    db.commit()
    return item
