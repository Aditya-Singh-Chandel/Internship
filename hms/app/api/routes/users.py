from typing import Annotated
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_admin, require_manager, get_current_user
from app.models.user import User
from app.models.hotel import Hotel
from app.models.role import Role
from app.core.roles import UserRole
from app.schemas import user as user_schema
from app.schemas.common import ActionResponse, SortOrder, StringFilterOperator, NumericFilterOperator
from app.services import user_service, role_service, token_service
from enum import Enum

class UserSortBy(str, Enum):
    name = "name"
    email = "email"
    created_at = "created_at"

router = APIRouter(prefix="/users", tags=["Users"])

ROLE_HIERARCHY = {
    UserRole.ADMIN.value: 4,
    UserRole.OWNER.value: 3,
    UserRole.MANAGER.value: 2,
    UserRole.RECEPTIONIST.value: 1,
    UserRole.CUSTOMER.value: 0,
    "guest": 0
}

@router.post("", response_model=user_schema.UserItemResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user: Annotated[user_schema.UserCreate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Create a new system user with strict hierarchy and ownership enforcement:
    - Admins can create Owners, Managers, Receptionists, and Customers.
    - Owners can only create Managers and Receptionists for hotels they own.
    - Managers can only create Receptionists for their assigned hotel.
    - An owner cannot be assigned to a hotel that already has an owner.
    """
    role_name = current_user.role.name.lower() if current_user.role else ""
    target_role = None
    if user.role_id:
        target_role = db.query(Role).filter(Role.id == user.role_id, Role.deleted_at.is_(None)).first()
    elif getattr(user, "role_name", None):
        target_role = role_service.get_or_create_role(db, user.role_name)
    else:
        target_role = role_service.get_or_create_role(db, UserRole.CUSTOMER.value)

    if not target_role:
        raise HTTPException(status_code=404, detail="The specified role does not exist.")

    target_role_name = target_role.name.lower()
    caller_level = ROLE_HIERARCHY.get(role_name, 0)
    target_level = ROLE_HIERARCHY.get(target_role_name, 0)

    if target_level >= caller_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Hierarchy violation: You cannot create a user with role '{target_role_name}' as it is at or above your clearance level."
        )

    # Parse target hotel IDs for owner (can be single hotel_id or list/string hotel_ids)
    owner_target_hotel_ids = []
    raw_hotel_ids = getattr(user, "hotel_ids", None)
    if raw_hotel_ids:
        if isinstance(raw_hotel_ids, str):
            owner_target_hotel_ids = [UUID(x.strip()) for x in raw_hotel_ids.split(",") if x.strip()]
        elif isinstance(raw_hotel_ids, list):
            owner_target_hotel_ids = [UUID(str(x)) for x in raw_hotel_ids if x]
    elif user.hotel_id:
        owner_target_hotel_ids = [user.hotel_id]

    if role_name == UserRole.ADMIN.value:
        if target_role_name == UserRole.OWNER.value:
            for hid in owner_target_hotel_ids:
                target_hotel = db.query(Hotel).filter(Hotel.id == hid, Hotel.deleted_at.is_(None)).first()
                if not target_hotel:
                    raise HTTPException(status_code=404, detail="The specified hotel does not exist.")
                if target_hotel.owner_id is not None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"This hotel ('{target_hotel.name}') already has an assigned owner. A property cannot have multiple owners."
                    )
    elif role_name == UserRole.OWNER.value:
        if target_role_name in [UserRole.ADMIN.value, UserRole.OWNER.value]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owners cannot create Admin or other Owner accounts.")
        # Verify or resolve hotel_id
        if user.hotel_id:
            hotel = db.query(Hotel).filter(Hotel.id == user.hotel_id, Hotel.deleted_at.is_(None)).first()
            if not hotel or hotel.owner_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. You do not own this hotel.")
        else:
            # Auto-assign if owner has exactly 1 hotel
            owned_hotels = db.query(Hotel).filter(Hotel.owner_id == current_user.id, Hotel.deleted_at.is_(None)).all()
            if len(owned_hotels) == 1:
                user.hotel_id = owned_hotels[0].id
            elif len(owned_hotels) > 1 and target_role_name in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
                raise HTTPException(status_code=400, detail="Please specify hotel_id for this staff member (you own multiple hotels).")
    elif role_name == UserRole.MANAGER.value:
        if target_role_name in [UserRole.ADMIN.value, UserRole.OWNER.value, UserRole.MANAGER.value]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers can only create Receptionist or Customer accounts.")
        if not current_user.hotel_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. You are not assigned to any hotel.")
        user.hotel_id = current_user.hotel_id

    if target_role_name == UserRole.OWNER.value:
        # Owners own hotels via Hotel.owner_id; they don't hold staff seats via user.hotel_id
        user.hotel_id = None

    user.role_id = target_role.id
    item = user_service.create_user(db=db, user=user)

    if target_role_name == UserRole.OWNER.value and owner_target_hotel_ids:
        for hid in owner_target_hotel_ids:
            th = db.query(Hotel).filter(Hotel.id == hid, Hotel.deleted_at.is_(None)).first()
            if th:
                th.owner_id = item.id
        db.commit()
        db.refresh(item)

    return {"success": True, "message": "User created successfully", "data": item}

@router.get("", response_model=user_schema.UserPaginatedResponse)
def read_users(
    name: str | None = Query(default=None),
    name_op: StringFilterOperator | None = Query(default=None),
    email: str | None = Query(default=None),
    email_op: StringFilterOperator | None = Query(default=None),
    phone: str | None = Query(default=None),
    role_id: UUID | None = Query(default=None),
    created_at: datetime | None = Query(default=None),
    created_at_op: NumericFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: UserSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    List users with strict role hierarchy:
    - An Admin cannot see another Admin, but sees everyone below it (Owner, Manager, Receptionist, Customer).
    - An Owner cannot see an Admin or another Owner, but sees everyone below it (Manager, Receptionist, Customer) for their owned hotels.
    - A Manager cannot see an Admin, Owner, or peer Manager, but sees Receptionists and Customers for their hotel.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user")}
    caller_role = current_user.role.name.lower() if current_user.role else "customer"
    caller_level = ROLE_HIERARCHY.get(caller_role, 0)

    if caller_level < 2:
        raise HTTPException(status_code=403, detail="Access denied. Only management can view team members.")

    # Strict hierarchy filter: Exclude any role whose hierarchy level >= caller_level
    excluded_roles = [r for r, lvl in ROLE_HIERARCHY.items() if lvl >= caller_level]
    query_params["_excluded_roles"] = excluded_roles

    if caller_role == UserRole.MANAGER.value:
        if not current_user.hotel_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. You are not assigned to any hotel.")
        query_params["hotel_id"] = current_user.hotel_id
    elif caller_role == UserRole.OWNER.value:
        owned_hotel_ids = [h.id for h in db.query(Hotel.id).filter(Hotel.owner_id == current_user.id, Hotel.deleted_at.is_(None)).all()]
        if "hotel_id" in query_params:
            if query_params["hotel_id"] not in owned_hotel_ids:
                raise HTTPException(status_code=403, detail="Access denied. You do not own this hotel.")
        else:
            query_params["_owner_hotel_ids"] = owned_hotel_ids

    return user_service.get_users(db=db, query_params=query_params)

@router.get("/{id}", response_model=user_schema.UserItemResponse)
def user_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    View user details with hierarchy enforcement:
    Cannot view peer or superior accounts.
    """
    target_user = user_service.get_user_by_id(db, id, include_deleted=include_deleted)
    role_name = current_user.role.name.lower() if current_user.role else ""
    caller_level = ROLE_HIERARCHY.get(role_name, 0)
    target_role = target_user.role.name.lower() if target_user.role else "customer"
    target_level = ROLE_HIERARCHY.get(target_role, 0)

    if current_user.id != id:
        if target_level >= caller_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot view peer or superior accounts.")

        if role_name == UserRole.OWNER.value:
            if not target_user.hotel_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot view users outside your hotels.")
            hotel = db.query(Hotel).filter(Hotel.id == target_user.hotel_id).first()
            if not hotel or hotel.owner_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot view users from hotels you do not own.")
        elif role_name == UserRole.MANAGER.value:
            if not current_user.hotel_id or target_user.hotel_id != current_user.hotel_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot view users from other hotels.")
        elif caller_level < 2:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot view other users' profiles.")

    return {"success": True, "message": "User retrieved successfully", "data": target_user}

@router.put("/{id}", response_model=user_schema.UserItemResponse)
def update_user(
    id: UUID,
    update_data: Annotated[user_schema.UserUpdate, Form()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile. Admins and Owners can update staff;
    users can update their own profile (non-admins cannot alter their role_id).
    """
    is_admin = current_user.role and current_user.role.name.lower() == UserRole.ADMIN.value
    if not is_admin and current_user.id != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot modify other users.")

    if not is_admin and update_data.role_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admins can change user roles.")

    target_user = user_service.get_user_by_id(db, id)
    is_owner_target = (target_user.role and target_user.role.name.lower() == UserRole.OWNER.value) or (
        update_data.role_name and update_data.role_name.lower() == UserRole.OWNER.value
    )

    if is_owner_target and (update_data.hotel_ids is not None or update_data.hotel_id is not None):
        new_hotel_ids = []
        raw_hotel_ids = update_data.hotel_ids
        if raw_hotel_ids is not None:
            if isinstance(raw_hotel_ids, str):
                new_hotel_ids = [UUID(x.strip()) for x in raw_hotel_ids.split(",") if x.strip()]
            elif isinstance(raw_hotel_ids, list):
                new_hotel_ids = [UUID(str(x)) for x in raw_hotel_ids if x]
        elif update_data.hotel_id:
            new_hotel_ids = [update_data.hotel_id]

        # Verify none of the target hotels already belong to a DIFFERENT owner
        for hid in new_hotel_ids:
            th = db.query(Hotel).filter(Hotel.id == hid, Hotel.deleted_at.is_(None)).first()
            if not th:
                raise HTTPException(status_code=404, detail="The specified hotel does not exist.")
            if th.owner_id is not None and th.owner_id != id:
                raise HTTPException(
                    status_code=400,
                    detail=f"This hotel ('{th.name}') already has an assigned owner. A property cannot have multiple owners."
                )

        # 1. Unassign hotels previously owned by this owner that are not in new_hotel_ids
        for ch in (target_user.owned_hotels or []):
            if ch.id not in new_hotel_ids:
                ch.owner_id = None

        # 2. Assign all selected hotels to this owner
        for hid in new_hotel_ids:
            th = db.query(Hotel).filter(Hotel.id == hid, Hotel.deleted_at.is_(None)).first()
            if th:
                th.owner_id = id

        db.commit()
        update_data.hotel_id = None

    item = user_service.update_user(db, id, update_data)
    return {"success": True, "message": "User updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_user(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a user account with strict hierarchy:
    Admins cannot delete other Admins. Owners cannot delete Admins or Owners.
    """
    if current_user.id == id:
        raise HTTPException(status_code=400, detail="Cannot delete your own active account.")

    target_user = user_service.get_user_by_id(db, id)
    role_name = current_user.role.name.lower() if current_user.role else ""
    caller_level = ROLE_HIERARCHY.get(role_name, 0)
    target_role = target_user.role.name.lower() if target_user.role else "customer"
    target_level = ROLE_HIERARCHY.get(target_role, 0)

    if target_level >= caller_level:
        raise HTTPException(status_code=403, detail="Access denied. Cannot delete peer or superior user accounts.")

    if role_name == UserRole.ADMIN.value:
        pass
    elif role_name == UserRole.OWNER.value:
        if not target_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. Cannot delete users outside your hotels.")
        hotel = db.query(Hotel).filter(Hotel.id == target_user.hotel_id, Hotel.deleted_at.is_(None)).first()
        if not hotel or hotel.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel this user belongs to.")
    elif role_name == UserRole.MANAGER.value:
        if not current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You are not assigned to any hotel.")
        if not target_user.hotel_id or target_user.hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only delete staff assigned to your hotel.")
    else:
        raise HTTPException(status_code=403, detail="Access denied. Insufficient permissions to delete users.")

    # If deleted user is an owner, unassign any hotels they owned
    if target_role == UserRole.OWNER.value:
        owned_hotels = db.query(Hotel).filter(Hotel.owner_id == id).all()
        for h in owned_hotels:
            h.owner_id = None

    # Revoke all active tokens/sessions for the deleted user
    token_service.revoke_all_user_tokens(db=db, user_id=id)

    item = user_service.delete_user(db, id)
    return {"success": True, "message": "User deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=user_schema.UserItemResponse, dependencies=[Depends(require_admin)])
def restore_user(id: UUID, db: Session = Depends(get_db)):
    """Only Admins can restore soft-deleted users."""
    item = user_service.restore_user(db, id)
    return {"success": True, "message": "User restored successfully", "data": item}
