from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_manager, get_optional_current_user
from app.models.user import User
from app.models.policy import Policy
from app.core.roles import UserRole
from app.schemas import policy as policy_schema
from app.schemas.common import ActionResponse, SortOrder, StringFilterOperator
from app.services import policy_service
from enum import Enum

class PolicySortBy(str, Enum):
    policy_type = "policy_type"

router = APIRouter(prefix="/policies", tags=["Policies"])

from app.models.hotel import Hotel
from app.utils.scoping_utils import resolve_and_verify_hotel_id

def _check_policy_ownership(db: Session, policy_id: UUID, current_user: User):
    role_name = current_user.role.name.lower() if current_user.role else ""
    if role_name == UserRole.ADMIN.value:
        return
    db_policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found.")
    hotel = db.query(Hotel).filter(Hotel.id == db_policy.hotel_id).first()
    if role_name == UserRole.OWNER.value:
        if hotel and hotel.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel for this policy.")
    elif role_name in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
        if current_user.hotel_id and db_policy.hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only modify policies for your assigned hotel.")

@router.post("", response_model=policy_schema.PolicyItemResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    policy: Annotated[policy_schema.PolicyCreate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Create a hotel policy.
    - If hotel_id is omitted, auto-resolves owner's or manager's hotel.
    - If provided, verifies owner or manager has rights to that hotel.
    """
    policy.hotel_id = resolve_and_verify_hotel_id(db, current_user, policy.hotel_id)
    item = policy_service.create_policy(db=db, policy=policy)
    return {"success": True, "message": "Policy created successfully", "data": item}

@router.get("", response_model=policy_schema.PolicyPaginatedResponse)
def read_policies(
    hotel_id: UUID | None = Query(default=None),
    policy_type: str | None = Query(default=None),
    policy_type_op: StringFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: PolicySortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    List policies with advanced filtering and sorting.
    Auto-scopes to staff's hotel if logged in without explicit filters.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user")}
    if current_user and current_user.role and current_user.role.name.lower() in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
        if current_user.hotel_id:
            if not hotel_id:
                query_params["hotel_id"] = current_user.hotel_id
            elif hotel_id != current_user.hotel_id:
                raise HTTPException(status_code=403, detail="Access denied. You can only view policies for your assigned hotel.")

    return policy_service.get_policies(db=db, query_params=query_params)

@router.get("/{id}", response_model=policy_schema.PolicyItemResponse)
def policy_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    item = policy_service.get_policy_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Policy retrieved successfully", "data": item}

@router.put("/{id}", response_model=policy_schema.PolicyItemResponse)
def update_policy(
    id: UUID,
    update_data: Annotated[policy_schema.PolicyUpdate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    _check_policy_ownership(db, id, current_user)
    item = policy_service.update_policy(db, id, update_data)
    return {"success": True, "message": "Policy updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_policy(
    id: UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    _check_policy_ownership(db, id, current_user)
    item = policy_service.delete_policy(db, id)
    return {"success": True, "message": "Policy deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=policy_schema.PolicyItemResponse)
def restore_policy(
    id: UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Restore a soft-deleted policy.
    """
    _check_policy_ownership(db, id, current_user)
    item = policy_service.restore_policy(db, id)
    return {"success": True, "message": "Policy restored successfully", "data": item}
