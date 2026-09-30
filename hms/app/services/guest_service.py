from app.utils.validation_utils import validate_string, validate_future_date
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.guest import Guest
from app.schemas.guest import GuestCreate

def create_guest(db: Session, guest: GuestCreate):
    _data_dict = guest.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_guest = Guest(**_data_dict)
    db.add(db_guest)
    db.commit()
    db.refresh(db_guest)
    return db_guest

def get_guests(db: Session):
    return db.query(Guest).all()

def get_guest_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Guest).filter(Guest.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Guest is not present.")
    return item

def update_guest(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Guest).filter(Guest.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Guest is not present.")

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

def delete_guest(db: Session, item_id: uuid.UUID):
    item = db.query(Guest).filter(Guest.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Guest is not present.")
    db.delete(item)
    db.commit()
    return item
