from app.utils.validation_utils import validate_string, validate_future_date
from datetime import date
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.role import Role
from app.schemas.role import RoleCreate

def create_role(db: Session, role: RoleCreate):
    db_role = Role(name=role.name)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role

def get_roles(db: Session):
    return db.query(Role).all()

def get_role_by_id(db: Session, item_id: uuid.UUID):
    item = db.query(Role).filter(Role.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Role is not present.")
    return item

def update_role(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Role).filter(Role.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Role is not present.")

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

def delete_role(db: Session, item_id: uuid.UUID):
    item = db.query(Role).filter(Role.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Role is not present.")
    db.delete(item)
    db.commit()
    return item
