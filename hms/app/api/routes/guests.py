from typing import Annotated
from datetime import datetime
from uuid import UUID
from enum import Enum
from fastapi import APIRouter, Depends, status, Form, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_staff, get_current_user
from app.models.user import User
from app.utils.scoping_utils import get_or_create_guest_for_user
from app.schemas import guest as guest_schema
from app.schemas.common import ActionResponse, SortOrder, StringFilterOperator, NumericFilterOperator
from app.services import guest_service

class GuestSortBy(str, Enum):
    name = "name"
    email = "email"
    created_at = "created_at"

router = APIRouter(prefix="/guests", tags=["Guests"])

@router.get("/me", response_model=guest_schema.GuestItemResponse)
def get_my_guest_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve or automatically provision the authenticated user's Guest profile.
    Accessible by any logged-in user (including customers).
    """
    guest = get_or_create_guest_for_user(db, current_user)
    return {"success": True, "message": "Guest profile retrieved successfully", "data": guest}

@router.put("/me", response_model=guest_schema.GuestItemResponse)
def update_my_guest_profile(
    update_data: Annotated[guest_schema.GuestUpdate, Form()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the authenticated user's own Guest profile.
    Accessible by any logged-in user without needing their guest UUID.
    """
    guest = get_or_create_guest_for_user(db, current_user)
    item = guest_service.update_guest(db, guest.id, update_data)
    return {"success": True, "message": "Guest profile updated successfully", "data": item}

@router.post("", response_model=guest_schema.GuestItemResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_staff)])
def create_guest(guest: Annotated[guest_schema.GuestCreate, Form()], db: Session = Depends(get_db)):
    """Staff only: Create a guest record."""
    item = guest_service.create_guest(db=db, guest=guest)
    return {"success": True, "message": "Guest created successfully", "data": item}

@router.get("", response_model=guest_schema.GuestPaginatedResponse, dependencies=[Depends(require_staff)])
def read_guests(
    name: str | None = Query(default=None),
    name_op: StringFilterOperator | None = Query(default=None),
    email: str | None = Query(default=None),
    email_op: StringFilterOperator | None = Query(default=None),
    phone: str | None = Query(default=None),
    id_document_number: str | None = Query(default=None),
    created_at: datetime | None = Query(default=None),
    created_at_op: NumericFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: GuestSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List guests with advanced filtering and sorting. (Staff only)
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return guest_service.get_guests(db=db, query_params=query_params)

@router.get("/{id}", response_model=guest_schema.GuestItemResponse, dependencies=[Depends(require_staff)])
def guest_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    """Staff only: View guest by ID."""
    item = guest_service.get_guest_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Guest retrieved successfully", "data": item}

@router.put("/{id}", response_model=guest_schema.GuestItemResponse, dependencies=[Depends(require_staff)])
def update_guest(id: UUID, update_data: Annotated[guest_schema.GuestUpdate, Form()], db: Session = Depends(get_db)):
    """Staff only: Update guest record."""
    item = guest_service.update_guest(db, id, update_data)
    return {"success": True, "message": "Guest updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse, dependencies=[Depends(require_staff)])
def delete_guest(id: UUID, db: Session = Depends(get_db)):
    """Staff only: Delete guest record."""
    item = guest_service.delete_guest(db, id)
    return {"success": True, "message": "Guest deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=guest_schema.GuestItemResponse, dependencies=[Depends(require_staff)])
def restore_guest(id: UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted guest and their reviews. (Staff only)
    """
    item = guest_service.restore_guest(db, id)
    return {"success": True, "message": "Guest restored successfully", "data": item}
