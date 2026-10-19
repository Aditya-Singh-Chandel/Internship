from app.utils.validation_utils import validate_string, validate_future_date
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
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

def get_roles(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(Role)
    query = filter_active(query, Role, query_params)
    query = apply_filters(query, Role, parsed["filters"])
    query = apply_sorting(query, Role, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "roles", query_params)

def get_role_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Role).filter(Role.id == item_id)
    if not include_deleted:
        query = query.filter(Role.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Role is not present.")
    return item

def update_role(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Role).filter(Role.id == item_id, Role.deleted_at.is_(None)).first()
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
    item = db.query(Role).filter(Role.id == item_id, Role.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Role is not present.")

    from app.models.user import User
    active_users = db.query(User).filter(User.role_id == item.id, User.deleted_at.is_(None)).count()
    if active_users > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role: {active_users} active user(s) are assigned to this role."
        )

    now = datetime.now(timezone.utc)
    item.deleted_at = now
    db.commit()
    db.refresh(item)
    return item

def restore_role(db: Session, item_id: uuid.UUID):
    item = db.query(Role).filter(Role.id == item_id, Role.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Role is not present or not deleted.")

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item
