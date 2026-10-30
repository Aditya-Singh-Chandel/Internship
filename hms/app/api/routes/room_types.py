from typing import Annotated
from decimal import Decimal
from datetime import date
from uuid import UUID
from enum import Enum
from fastapi import APIRouter, Depends, status, Form, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_manager, get_optional_current_user
from app.models.user import User
from app.core.roles import UserRole
from app.schemas import room_type as room_type_schema
from app.schemas.common import ActionResponse, SortOrder, StringFilterOperator, NumericFilterOperator
from app.services import room_type_service

class RoomTypeSortBy(str, Enum):
    name = "name"
    base_price = "base_price"
    guests_allowed = "guests_allowed"
from app.utils.scoping_utils import resolve_and_verify_hotel_id

router = APIRouter(prefix="/room-types", tags=["Room Types"])

@router.post("", response_model=room_type_schema.RoomTypeItemResponse, status_code=status.HTTP_201_CREATED)
def create_room_type(
    room_type: Annotated[room_type_schema.RoomTypeCreate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Create a room type.
    - If hotel_id is omitted, it is automatically resolved from the owner's or manager's hotel.
    - If hotel_id is provided, verifies owner or manager has rights for that hotel.
    """
    room_type.hotel_id = resolve_and_verify_hotel_id(db, current_user, room_type.hotel_id)
    item = room_type_service.create_room_type(db=db, room_type=room_type)
    return {"success": True, "message": "Room type created successfully", "data": item}

@router.get("", response_model=room_type_schema.RoomTypePaginatedResponse)
def read_room_types(
    hotel_id: UUID | None = Query(default=None),
    checkin_date: date | None = Query(default=None, description="Check-in date (YYYY-MM-DD) to filter room types by availability"),
    checkout_date: date | None = Query(default=None, description="Check-out date (YYYY-MM-DD) to filter room types by availability"),
    rooms_count: int | None = Query(default=1, ge=1, description="Number of rooms required to filter room types by availability"),
    only_available: bool = Query(default=False, description="If true, only returns categories with physical rooms available"),
    name: str | None = Query(default=None),
    name_op: StringFilterOperator | None = Query(default=None),
    base_price: Decimal | None = Query(default=None),
    base_price_op: NumericFilterOperator | None = Query(default=None),
    guests_allowed: int | None = Query(default=None),
    guests_allowed_op: NumericFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: RoomTypeSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    List room types with advanced filtering and sorting.
    If hotel_id is omitted and user is hotel staff, automatically scopes to their hotel.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user")}

    # Auto-scope staff to their hotel if hotel_id was not explicitly specified
    if hotel_id is None and current_user and current_user.role:
        role_name = current_user.role.name.lower()
        if role_name in [UserRole.RECEPTIONIST.value, UserRole.MANAGER.value] and current_user.hotel_id:
            query_params["hotel_id"] = current_user.hotel_id

    return room_type_service.get_room_types(db=db, query_params=query_params)

@router.get("/{id}", response_model=room_type_schema.RoomTypeItemResponse)
def room_type_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    item = room_type_service.get_room_type_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Room type retrieved successfully", "data": item}

@router.put("/{id}", response_model=room_type_schema.RoomTypeItemResponse, dependencies=[Depends(require_manager)])
def update_room_type(id: UUID, update_data: Annotated[room_type_schema.RoomTypeUpdate, Form()], db: Session = Depends(get_db)):
    item = room_type_service.update_room_type(db, id, update_data)
    return {"success": True, "message": "Room type updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse, dependencies=[Depends(require_manager)])
def delete_room_type(id: UUID, db: Session = Depends(get_db)):
    item = room_type_service.delete_room_type(db, id)
    return {"success": True, "message": "Room type deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=room_type_schema.RoomTypeItemResponse, dependencies=[Depends(require_manager)])
def restore_room_type(id: UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted room type and its cascadingly deleted rooms, amenities, and media.
    """
    item = room_type_service.restore_room_type(db, id)
    return {"success": True, "message": "Room type restored successfully", "data": item}
