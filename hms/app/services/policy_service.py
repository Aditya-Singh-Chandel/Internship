from app.utils.validation_utils import validate_string, validate_future_date
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.policy import Policy
from app.schemas.policy import PolicyCreate

def create_policy(db: Session, policy: PolicyCreate):
    _data_dict = policy.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): _data_dict[k] = validate_string(k, v)
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_policy = Policy(**_data_dict)
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy

def get_policies(db: Session, hotel_id: str = None):
    query = db.query(Policy)
    if hotel_id:
        query = query.filter(Policy.hotel_id == hotel_id)
    return query.all()

def get_policy_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Policy).filter(Policy.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Policy is not present.")
    return item

def update_policy(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Policy).filter(Policy.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Policy is not present.")

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

def delete_policy(db: Session, item_id: uuid.UUID):
    item = db.query(Policy).filter(Policy.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Policy is not present.")
    db.delete(item)
    db.commit()
    return item
