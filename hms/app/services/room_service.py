from app.utils.validation_utils import validate_string, validate_future_date
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.room import Room
from app.schemas.room import RoomCreate

def create_room(db: Session, room: RoomCreate):
    _data_dict = room.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_room = Room(**_data_dict)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room

def get_rooms(db: Session, room_type_id: str = None):
    query = db.query(Room)
    if room_type_id:
        query = query.filter(Room.room_type_id == room_type_id)
    return query.all()

def get_room_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Room).filter(Room.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Room is not present.")
    return item

def update_room(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Room).filter(Room.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Room is not present.")

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

def delete_room(db: Session, item_id: uuid.UUID):
    item = db.query(Room).filter(Room.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Room is not present.")
    db.delete(item)
    db.commit()
    return item
