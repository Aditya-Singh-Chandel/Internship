from app.utils.validation_utils import (
    validate_string, validate_future_date,
    validate_room_type_belongs_to_hotel,
)
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.media import Media
from app.schemas.media import MediaCreate

def create_media(db: Session, media: MediaCreate):
    _data_dict = media.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)

    # Cross-reference: if both hotel_id and room_type_id are set, room_type must belong to the hotel
    if _data_dict.get("hotel_id") and _data_dict.get("room_type_id"):
        validate_room_type_belongs_to_hotel(db, _data_dict["room_type_id"], _data_dict["hotel_id"])

    db_media = Media(**_data_dict)
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    return db_media

def get_media(db: Session, hotel_id: str = None, room_type_id: str = None):
    query = db.query(Media)
    if hotel_id:
        query = query.filter(Media.hotel_id == hotel_id)
    if room_type_id:
        query = query.filter(Media.room_type_id == room_type_id)
    return query.all()

def get_media_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Media).filter(Media.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Media is not present.")
    return item

def update_media(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Media).filter(Media.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Media is not present.")

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

def delete_media(db: Session, item_id: uuid.UUID):
    item = db.query(Media).filter(Media.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Media is not present.")
    db.delete(item)
    db.commit()
    return item
