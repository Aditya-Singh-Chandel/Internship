from app.utils.validation_utils import validate_string, validate_future_date
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.hotel import Hotel
from app.schemas.hotel import HotelCreate

def create_hotel(db: Session, hotel: HotelCreate):
    _data_dict = hotel.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_hotel = Hotel(**_data_dict)
    db.add(db_hotel)
    db.commit()
    db.refresh(db_hotel)
    return db_hotel

def get_hotels(db: Session):
    return db.query(Hotel).all()

def get_hotel_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Hotel).filter(Hotel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Hotel is not present.")
    return item

def update_hotel(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Hotel).filter(Hotel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Hotel is not present.")

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

def delete_hotel(db: Session, item_id: uuid.UUID):
    item = db.query(Hotel).filter(Hotel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Hotel is not present.")
    db.delete(item)
    db.commit()
    return item
