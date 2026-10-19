from app.utils.validation_utils import validate_string, validate_future_date
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from datetime import date, datetime, timezone
from fastapi import HTTPException
import uuid
from sqlalchemy.orm import Session
from app.models.policy import Policy
from app.schemas.policy import PolicyCreate


def create_policy(db: Session, policy: PolicyCreate):
    _data_dict = policy.model_dump()
    for k, v in _data_dict.items():
        if isinstance(v, str): 
            val = validate_string(k, v)
            if k == 'description' and not val:
                raise HTTPException(status_code=400, detail="Policy description cannot be empty.")
            _data_dict[k] = val
        elif isinstance(v, date) and k in ["checkin_date", "checkout_date"]: _data_dict[k] = validate_future_date(k, v)
    db_policy = Policy(**_data_dict)
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy

def get_policies(db: Session, query_params: dict | None = None):
    if query_params is None:
        query_params = {}

    parsed = extract_filters(query_params)

    query = db.query(Policy)
    query = filter_active(query, Policy, query_params)
    query = apply_filters(query, Policy, parsed["filters"])
    query = apply_sorting(query, Policy, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "policies", query_params)

def get_policy_by_id(db: Session, item_id: uuid.UUID, include_deleted: bool = False):
    query = db.query(Policy).filter(Policy.id == item_id)
    if not include_deleted:
        query = query.filter(Policy.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This Policy is not present.")
    return item

def update_policy(db: Session, item_id: uuid.UUID, update_data):
    item = db.query(Policy).filter(Policy.id == item_id, Policy.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Policy is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_data_dict.items():
        if isinstance(value, str):
            val = validate_string(key, value)
            if key == 'description' and not val:
                raise HTTPException(status_code=400, detail="Policy description cannot be empty.")
            value = val
        elif isinstance(value, date) and key in ["checkin_date", "checkout_date"]:
            value = validate_future_date(key, value)
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item

def delete_policy(db: Session, item_id: uuid.UUID):
    item = db.query(Policy).filter(Policy.id == item_id, Policy.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Policy is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now
    db.commit()
    db.refresh(item)
    return item

def restore_policy(db: Session, item_id: uuid.UUID):
    item = db.query(Policy).filter(Policy.id == item_id, Policy.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This Policy is not present or not deleted.")

    from app.models.hotel import Hotel
    hotel = db.query(Hotel).filter(Hotel.id == item.hotel_id, Hotel.deleted_at.is_(None)).first()
    if not hotel:
        raise HTTPException(status_code=400, detail="Cannot restore policy: associated hotel is deleted.")

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item
