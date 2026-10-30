from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.roles import UserRole
from app.core.security import get_password_hash, verify_password
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserRegister
from app.services.role_service import get_or_create_role
from app.utils.query_utils import extract_filters, apply_filters, apply_sorting, filter_active, paginate_and_format
from app.utils.validation_utils import validate_string

def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.strip().lower(), User.deleted_at.is_(None)).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def register_user(db: Session, user_data: UserRegister) -> User:
    # Check if email is already taken
    existing = db.query(User).filter(User.email == user_data.email.strip().lower(), User.deleted_at.is_(None)).first()
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    role = None
    if user_data.role_id:
        role = db.query(Role).filter(Role.id == user_data.role_id, Role.deleted_at.is_(None)).first()
        if not role:
            raise HTTPException(status_code=404, detail="The specified role_id does not exist.")
        if role.name.lower() in [UserRole.ADMIN.value, UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
            raise HTTPException(status_code=403, detail="Self-registration for staff roles (admin, manager, receptionist) is not permitted. Staff must be created by a Hotel Owner or Administrator.")
    elif getattr(user_data, "role_name", None):
        clean_role_name = user_data.role_name.strip().lower()
        if clean_role_name in [UserRole.ADMIN.value, UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
            raise HTTPException(status_code=403, detail="Self-registration for staff roles (admin, manager, receptionist) is not permitted. Staff must be created by a Hotel Owner or Administrator.")
        role = get_or_create_role(db, clean_role_name)
    else:
        role = get_or_create_role(db, UserRole.CUSTOMER.value)

    hashed_pwd = get_password_hash(user_data.password)
    db_user = User(
        role_id=role.id,
        hotel_id=getattr(user_data, "hotel_id", None),
        name=user_data.name.strip(),
        email=user_data.email.strip().lower(),
        password_hash=hashed_pwd,
        phone=user_data.phone
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_user(db: Session, user: UserCreate):
    existing = db.query(User).filter(User.email == user.email.strip().lower(), User.deleted_at.is_(None)).first()
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    role = None
    if user.role_id:
        role = db.query(Role).filter(Role.id == user.role_id, Role.deleted_at.is_(None)).first()
        if not role:
            raise HTTPException(status_code=404, detail="The specified role_id does not exist.")
    elif getattr(user, "role_name", None):
        role = get_or_create_role(db, user.role_name)
    else:
        role = get_or_create_role(db, UserRole.CUSTOMER.value)

    real_hashed_password = get_password_hash(user.password)
    db_user = User(
        role_id=role.id,
        hotel_id=getattr(user, "hotel_id", None),
        name=user.name.strip(),
        email=user.email.strip().lower(),
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

    excluded_roles = query_params.pop("_excluded_roles", None)
    owner_hotel_ids = query_params.pop("_owner_hotel_ids", None)

    parsed = extract_filters(query_params)

    query = db.query(User).options(
        joinedload(User.role),
        joinedload(User.hotel),
        joinedload(User.owned_hotels)
    )

    if excluded_roles:
        query = query.join(Role, User.role_id == Role.id).filter(~Role.name.in_(excluded_roles))

    if owner_hotel_ids is not None:
        query = query.filter(User.hotel_id.in_(owner_hotel_ids))

    query = filter_active(query, User, query_params)
    query = apply_filters(query, User, parsed["filters"])
    query = apply_sorting(query, User, parsed["sort_by"], parsed["sort_order"])

    return paginate_and_format(query, "users", query_params)

def get_user_by_id(db: Session, item_id: UUID, include_deleted: bool = False):
    query = db.query(User).options(
        joinedload(User.role),
        joinedload(User.hotel),
        joinedload(User.owned_hotels)
    ).filter(User.id == item_id)
    if not include_deleted:
        query = query.filter(User.deleted_at.is_(None))
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="This User is not present.")
    return item

def update_user(db: Session, item_id: UUID, update_data):
    item = db.query(User).options(
        joinedload(User.role),
        joinedload(User.hotel),
        joinedload(User.owned_hotels)
    ).filter(User.id == item_id, User.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This User is not present.")

    update_data_dict = update_data.model_dump(exclude_unset=True)
    update_data_dict.pop("hotel_ids", None)
    if "role_name" in update_data_dict and update_data_dict["role_name"]:
        role_obj = get_or_create_role(db, update_data_dict.pop("role_name"))
        item.role_id = role_obj.id

    for key, value in update_data_dict.items():
        if hasattr(item, key):
            if isinstance(value, str):
                value = validate_string(key, value)
            setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item

def delete_user(db: Session, item_id: UUID):
    item = db.query(User).filter(User.id == item_id, User.deleted_at.is_(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This User is not present.")

    now = datetime.now(timezone.utc)
    item.deleted_at = now
    db.commit()
    db.refresh(item)
    return item

def restore_user(db: Session, item_id: UUID):
    item = db.query(User).filter(User.id == item_id, User.deleted_at.isnot(None)).first()
    if not item:
        raise HTTPException(status_code=404, detail="This User is not present or not deleted.")

    if item.role_id:
        role = db.query(Role).filter(Role.id == item.role_id, Role.deleted_at.is_(None)).first()
        if not role:
            raise HTTPException(status_code=400, detail="Cannot restore user: associated role is deleted.")

    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return item

