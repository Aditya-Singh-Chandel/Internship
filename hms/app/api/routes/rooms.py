from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import room as room_schema
from app.schemas.room import RoomStatus
from app.services import room_service


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


class RoomSortBy(str, Enum):
    room_number = "room_number"
    floor = "floor"
    status = "status"

router = APIRouter(prefix="/rooms", tags=["Rooms"])

@router.post("", response_model=room_schema.RoomListResponse, status_code=status.HTTP_201_CREATED)
def create_room(room: Annotated[room_schema.RoomCreate, Form()], db: Session = Depends(get_db)):
    return {"rooms": [room_service.create_room(db=db, room=room)]}

@router.post("/bulk", response_model=room_schema.RoomListResponse, status_code=status.HTTP_201_CREATED)
def create_rooms_bulk(bulk_data: room_schema.BulkRoomCreate, db: Session = Depends(get_db)):
    """
    Bulk create multiple physical rooms under a single room type using JSON.
    """
    return {"rooms": room_service.create_rooms_bulk(db=db, bulk_data=bulk_data)}

@router.get("", response_model=room_schema.RoomListResponse)
def read_rooms(
    room_type_id: UUID | None = Query(default=None),
    room_number: str | None = Query(default=None),
    floor: int | None = Query(default=None),
    status: RoomStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: RoomSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List rooms with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return room_service.get_rooms(db=db, query_params=query_params)

@router.get("/{id}", response_model=room_schema.RoomListResponse)
def room_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"rooms": [room_service.get_room_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=room_schema.RoomListResponse)
def update_room(id: uuid.UUID, update_data: Annotated[room_schema.RoomUpdate, Form()], db: Session = Depends(get_db)):
    return {"rooms": [room_service.update_room(db, id, update_data)]}

@router.delete("/{id}", response_model=room_schema.RoomListResponse)
def delete_room(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"rooms": [room_service.delete_room(db, id)]}

@router.post("/{id}/restore", response_model=room_schema.RoomListResponse)
def restore_room(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted physical room.
    """
    return {"rooms": [room_service.restore_room(db, id)]}
