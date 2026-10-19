from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import room_type as room_type_schema
from app.services import room_type_service


from enum import Enum

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class StringFilterOperator(str, Enum):
    eq = "eq"
    like = "like"

class NumericFilterOperator(str, Enum):
    eq = "eq"
    lt = "lt"
    gt = "gt"
    lte = "lte"
    gte = "gte"


class RoomTypeSortBy(str, Enum):
    name = "name"
    base_price = "base_price"
    guests_allowed = "guests_allowed"
router = APIRouter(prefix="/room-types", tags=["Room Types"])

@router.post("", response_model=room_type_schema.RoomTypeListResponse, status_code=status.HTTP_201_CREATED)
def create_room_type(room_type: Annotated[room_type_schema.RoomTypeCreate, Form()], db: Session = Depends(get_db)):
    return {"room_types": [room_type_service.create_room_type(db=db, room_type=room_type)]}

@router.get("", response_model=room_type_schema.RoomTypeListResponse)
def read_room_types(
    hotel_id: UUID | None = Query(default=None),
    checkin_date: date | None = Query(default=None, description="Check-in date (YYYY-MM-DD) to filter room types by availability"),
    checkout_date: date | None = Query(default=None, description="Check-out date (YYYY-MM-DD) to filter room types by availability"),
    rooms_count: int | None = Query(default=1, ge=1, description="Number of rooms required to filter room types by availability"),
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
    db: Session = Depends(get_db)
):
    """
    List room types with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return room_type_service.get_room_types(db=db, query_params=query_params)

@router.get("/{id}", response_model=room_type_schema.RoomTypeListResponse)
def room_type_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"room_types": [room_type_service.get_room_type_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=room_type_schema.RoomTypeListResponse)
def update_room_type(id: uuid.UUID, update_data: Annotated[room_type_schema.RoomTypeUpdate, Form()], db: Session = Depends(get_db)):
    return {"room_types": [room_type_service.update_room_type(db, id, update_data)]}

@router.delete("/{id}", response_model=room_type_schema.RoomTypeListResponse)
def delete_room_type(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"room_types": [room_type_service.delete_room_type(db, id)]}

@router.post("/{id}/restore", response_model=room_type_schema.RoomTypeListResponse)
def restore_room_type(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted room type and its cascadingly deleted rooms, amenities, and media.
    """
    return {"room_types": [room_type_service.restore_room_type(db, id)]}
