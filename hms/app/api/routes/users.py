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
from app.services import user_service, role_service
from enum import Enum

class UserSortBy(str, Enum):
    name = "name"
    email = "email"
    created_at = "created_at"

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=user_schema.UserItemResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user: Annotated[user_schema.UserCreate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Create a new system user.
    - Admins can create any user (admin, owner, manager, receptionist, customer).
    - Owners can create managers and receptionists for hotels they own.
    - Managers can only create receptionists for their assigned hotel.
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

    if role_name == UserRole.ADMIN.value:
        pass  # Admins have no restrictions
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
            raise HTTPException(status_code=403, detail="Access denied. You are not assigned to any hotel.")
        user.hotel_id = current_user.hotel_id

    user.role_id = target_role.id
    item = user_service.create_user(db=db, user=user)
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
    List users with advanced filtering and sorting.
    - Admins see all users.
    - Owners see users across hotels they own.
    - Managers see users within their assigned hotel.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user")}
    role_name = current_user.role.name.lower() if current_user.role else ""

    if role_name == UserRole.MANAGER.value and current_user.hotel_id:
        query_params["hotel_id"] = current_user.hotel_id
    elif role_name == UserRole.OWNER.value:
        owned_hotel_ids = [h.id for h in db.query(Hotel.id).filter(Hotel.owner_id == current_user.id).all()]
        if "hotel_id" in query_params:
            if query_params["hotel_id"] not in owned_hotel_ids:
                raise HTTPException(status_code=403, detail="Access denied. You do not own this hotel.")

    return user_service.get_users(db=db, query_params=query_params)

@router.get("/{id}", response_model=user_schema.UserItemResponse)
def user_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    View user details.
    - Admins can view any user.
    - Owners can view users in their hotels.
    - Managers can view users in their own hotel.
    - Regular users can view their own profile.
    """
    target_user = user_service.get_user_by_id(db, id, include_deleted=include_deleted)
    role_name = current_user.role.name.lower() if current_user.role else ""

    if role_name == UserRole.ADMIN.value:
        pass
    elif role_name == UserRole.OWNER.value:
        if current_user.id != id:
            if not target_user.hotel_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot view users outside your hotels.")
            hotel = db.query(Hotel).filter(Hotel.id == target_user.hotel_id).first()
            if not hotel or hotel.owner_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot view users from hotels you do not own.")
    elif role_name == UserRole.MANAGER.value:
        if current_user.id != id and (not current_user.hotel_id or target_user.hotel_id != current_user.hotel_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Cannot view users from other hotels.")
    else:
        if current_user.id != id:
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

    item = user_service.update_user(db, id, update_data)
    return {"success": True, "message": "User updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_user(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a user account.
    - Admins can delete any user.
    - Owners can delete staff assigned to hotels they own.
    """
    from app.models.hotel import Hotel
    role_name = current_user.role.name.lower() if current_user.role else ""
    if role_name == UserRole.ADMIN.value:
        pass
    elif role_name == UserRole.OWNER.value:
        target_user = user_service.get_user_by_id(db, id)
        if not target_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. Cannot delete users outside your hotels.")
        hotel = db.query(Hotel).filter(Hotel.id == target_user.hotel_id).first()
        if not hotel or hotel.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel this user belongs to.")
    else:
        raise HTTPException(status_code=403, detail="Access denied. Insufficient permissions to delete users.")

    item = user_service.delete_user(db, id)
    return {"success": True, "message": "User deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=user_schema.UserItemResponse, dependencies=[Depends(require_admin)])
def restore_user(id: UUID, db: Session = Depends(get_db)):
    """Only Admins can restore soft-deleted users."""
    item = user_service.restore_user(db, id)
    return {"success": True, "message": "User restored successfully", "data": item}
