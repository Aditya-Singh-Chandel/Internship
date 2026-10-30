from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_manager, get_optional_current_user
from app.models.user import User
from app.models.room import Room
from app.models.room_type import RoomType
from app.core.roles import UserRole
from app.schemas import room as room_schema
from app.schemas.room import RoomStatus
from app.schemas.common import ItemResponse, ActionResponse, SortOrder
from app.services import room_service
from enum import Enum

class RoomSortBy(str, Enum):
    room_number = "room_number"
    floor = "floor"
    status = "status"

router = APIRouter(prefix="/rooms", tags=["Rooms"])

from app.models.hotel import Hotel

def _check_room_ownership(db: Session, room_id: UUID, current_user: User):
    role_name = current_user.role.name.lower() if current_user.role else ""
    if role_name == UserRole.ADMIN.value:
        return
    db_room = db.query(Room).filter(Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="This Room is not present.")
    rt = db.query(RoomType).filter(RoomType.id == db_room.room_type_id).first()
    if not rt:
        return
    hotel = db.query(Hotel).filter(Hotel.id == rt.hotel_id).first()
    if role_name == UserRole.OWNER.value:
        if hotel and hotel.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel for this room.")
    elif role_name in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
        if current_user.hotel_id and rt.hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only modify rooms for your assigned hotel.")

@router.post("", response_model=room_schema.RoomItemResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    room: Annotated[room_schema.RoomCreate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Create a physical room under a room type.
    Verifies that the target room type belongs to owner's or manager's hotel.
    """
    rt = db.query(RoomType).filter(RoomType.id == room.room_type_id, RoomType.deleted_at.is_(None)).first()
    if not rt:
        raise HTTPException(status_code=404, detail="The specified room_type does not exist.")
    role_name = current_user.role.name.lower() if current_user.role else ""
    if role_name == UserRole.OWNER.value:
        hotel = db.query(Hotel).filter(Hotel.id == rt.hotel_id).first()
        if hotel and hotel.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel for this room type.")
    elif role_name == UserRole.MANAGER.value:
        if current_user.hotel_id and rt.hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You cannot create rooms under another hotel's room type.")

    item = room_service.create_room(db=db, room=room)
    return {"success": True, "message": "Room created successfully", "data": item}

@router.post("/bulk", response_model=ItemResponse[list[room_schema.RoomItem]], status_code=status.HTTP_201_CREATED)
def create_rooms_bulk(
    bulk_data: room_schema.BulkRoomCreate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Bulk create multiple physical rooms under a single room type using JSON.
    Verifies that the target room type belongs to owner's or manager's hotel.
    """
    rt = db.query(RoomType).filter(RoomType.id == bulk_data.room_type_id, RoomType.deleted_at.is_(None)).first()
    if not rt:
        raise HTTPException(status_code=404, detail="The specified room_type does not exist.")
    role_name = current_user.role.name.lower() if current_user.role else ""
    if role_name == UserRole.OWNER.value:
        hotel = db.query(Hotel).filter(Hotel.id == rt.hotel_id).first()
        if hotel and hotel.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel for this room type.")
    elif role_name == UserRole.MANAGER.value:
        if current_user.hotel_id and rt.hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You cannot create rooms under another hotel's room type.")

    items = room_service.create_rooms_bulk(db=db, bulk_data=bulk_data)
    return {"success": True, "message": f"{len(items)} rooms created successfully", "data": items}

@router.get("", response_model=room_schema.RoomPaginatedResponse)
def read_rooms(
    hotel_id: UUID | None = Query(default=None, description="Filter rooms by hotel"),
    room_type_id: UUID | None = Query(default=None),
    room_number: str | None = Query(default=None),
    floor: int | None = Query(default=None),
    status: RoomStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: RoomSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    List rooms with advanced filtering and sorting.
    Auto-scopes to manager's hotel if logged in without explicit filters.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user")}
    if current_user and current_user.role:
        r_name = current_user.role.name.lower()
        if r_name in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
            if not current_user.hotel_id:
                raise HTTPException(status_code=403, detail="Access denied. You are not assigned to any hotel.")
            if not hotel_id and not room_type_id:
                query_params["hotel_id"] = current_user.hotel_id
            elif hotel_id and hotel_id != current_user.hotel_id:
                raise HTTPException(status_code=403, detail="Access denied. You can only view rooms for your assigned hotel.")
            elif room_type_id:
                rt = db.query(RoomType).filter(RoomType.id == room_type_id).first()
                if rt and rt.hotel_id != current_user.hotel_id:
                    raise HTTPException(status_code=403, detail="Access denied. You can only view rooms for your assigned hotel.")
        elif r_name == UserRole.OWNER.value:
            from app.models.hotel import Hotel
            owned_hotel_ids = [h.id for h in db.query(Hotel.id).filter(Hotel.owner_id == current_user.id, Hotel.deleted_at.is_(None)).all()]
            if not owned_hotel_ids:
                raise HTTPException(status_code=403, detail="Access denied. You do not own any hotel.")
            if hotel_id and hotel_id not in owned_hotel_ids:
                raise HTTPException(status_code=403, detail="Access denied. You do not own this hotel.")
            if not hotel_id:
                query_params["_owner_hotel_ids"] = owned_hotel_ids

    return room_service.get_rooms(db=db, query_params=query_params)

@router.get("/{id}", response_model=room_schema.RoomItemResponse)
def room_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    item = room_service.get_room_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Room retrieved successfully", "data": item}

@router.put("/{id}", response_model=room_schema.RoomItemResponse)
def update_room(
    id: UUID,
    update_data: Annotated[room_schema.RoomUpdate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    _check_room_ownership(db, id, current_user)
    if update_data.room_type_id and current_user.hotel_id:
        rt = db.query(RoomType).filter(RoomType.id == update_data.room_type_id).first()
        if rt and rt.hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. Target room type belongs to another hotel.")
    item = room_service.update_room(db, id, update_data)
    return {"success": True, "message": "Room updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_room(
    id: UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    _check_room_ownership(db, id, current_user)
    item = room_service.delete_room(db, id)
    return {"success": True, "message": "Room deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=room_schema.RoomItemResponse)
def restore_room(
    id: UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Restore a soft-deleted physical room.
    """
    _check_room_ownership(db, id, current_user)
    item = room_service.restore_room(db, id)
    return {"success": True, "message": "Room restored successfully", "data": item}
