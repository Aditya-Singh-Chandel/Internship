from app.utils.validation_utils import validate_string, validate_future_date
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate

import hashlib
import os


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

def create_user(db: Session, user: UserCreate):
    real_hashed_password = hash_password(user.password)
    db_user = User(
        role_id=user.role_id,
        name=user.name,
        email=user.email,
        password_hash=real_hashed_password,
        phone=user.phone
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(User)
    query = filter_active(query, User, query_params)
    query = apply_filters(query, User, parsed["filters"])
    query = apply_sorting(query, User, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "users", query_params)

def get_user_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(User).filter(User.id == item_id)
    if not include_deleted:
        query = query.filter(User.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This User is not present.")
    return item

def update_user(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(User).filter(User.id == item_id, User.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This User is not present.")

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

def delete_user(db: Session, item_id: uuid.UUID):
    item = db.query(User).filter(User.id == item_id, User.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This User is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now
    db.commit()
    db.refresh(item)
    return item

def restore_user(db: Session, item_id: uuid.UUID):
    item = db.query(User).filter(User.id == item_id, User.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This User is not present or not deleted.")

    if item.role_id:
        from app.models.role import Role
        role = db.query(Role).filter(Role.id == item.role_id, Role.deleted_at.is_(None)).first()
        if not role:
            raise HTTPException(status_code=400, detail="Cannot restore user: associated role is deleted.")

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item
