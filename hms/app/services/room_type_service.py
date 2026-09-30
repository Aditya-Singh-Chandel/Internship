from app.utils.validation_utils import validate_string, validate_future_date
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.room_type import RoomType
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

def get_room_types(db: Session, hotel_id: str = None):
    query = db.query(RoomType)
    if hotel_id:
        query = query.filter(RoomType.hotel_id == hotel_id)
    return query.all()

def get_room_type_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(RoomType).filter(RoomType.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This RoomType is not present.")
    return item

def update_room_type(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(RoomType).filter(RoomType.id == item_id).first()
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
    item = db.query(RoomType).filter(RoomType.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This RoomType is not present.")
    db.delete(item)
    db.commit()
    return item
