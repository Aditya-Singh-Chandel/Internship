from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_manager, get_optional_current_user
from app.models.user import User
from app.models.amenity import Amenity
from app.models.room_type import RoomType
from app.core.roles import UserRole
from app.schemas import amenity as amenity_schema
from app.schemas.common import ItemResponse, ActionResponse, SortOrder, StringFilterOperator
from app.services import amenity_service
from enum import Enum

class AmenitySortBy(str, Enum):
    name = "name"

router = APIRouter(prefix="/amenities", tags=["Amenities"])

from app.models.hotel import Hotel
from app.utils.scoping_utils import resolve_and_verify_hotel_id

def _check_amenity_ownership(db: Session, amenity_id: UUID, current_user: User):
    role_name = current_user.role.name.lower() if current_user.role else ""
    if role_name == UserRole.ADMIN.value:
        return
    db_amenity = db.query(Amenity).filter(Amenity.id == amenity_id).first()
    if not db_amenity:
        raise HTTPException(status_code=404, detail="Amenity not found.")
    effective_hotel_id = db_amenity.hotel_id
    if not effective_hotel_id and db_amenity.room_type_id:
        rt = db.query(RoomType).filter(RoomType.id == db_amenity.room_type_id).first()
        effective_hotel_id = rt.hotel_id if rt else None

    if effective_hotel_id:
        hotel = db.query(Hotel).filter(Hotel.id == effective_hotel_id).first()
        if role_name == UserRole.OWNER.value:
            if hotel and hotel.owner_id != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel for this amenity.")
        elif role_name in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
            if current_user.hotel_id and effective_hotel_id != current_user.hotel_id:
                raise HTTPException(status_code=403, detail="Access denied. You can only modify amenities for your assigned hotel.")

@router.post("", response_model=amenity_schema.AmenityItemResponse, status_code=status.HTTP_201_CREATED)
def create_amenity(
    amenity: Annotated[amenity_schema.AmenityCreate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Create an amenity.
    - If hotel_id is omitted and room_type_id is not specified, auto-resolves owner/manager's hotel_id.
    - If room_type_id is specified, verifies it belongs to the owner's or manager's hotel.
    """
    if not amenity.hotel_id and not amenity.room_type_id:
        amenity.hotel_id = resolve_and_verify_hotel_id(db, current_user, None)
    elif amenity.hotel_id:
        amenity.hotel_id = resolve_and_verify_hotel_id(db, current_user, amenity.hotel_id)
    elif amenity.room_type_id:
        rt = db.query(RoomType).filter(RoomType.id == amenity.room_type_id, RoomType.deleted_at.is_(None)).first()
        if not rt:
            raise HTTPException(status_code=404, detail="The specified room_type does not exist.")
        role_name = current_user.role.name.lower() if current_user.role else ""
        if role_name == UserRole.OWNER.value:
            hotel = db.query(Hotel).filter(Hotel.id == rt.hotel_id).first()
            if hotel and hotel.owner_id != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel for this room type.")
        elif role_name == UserRole.MANAGER.value:
            if current_user.hotel_id and rt.hotel_id != current_user.hotel_id:
                raise HTTPException(status_code=403, detail="Access denied. The specified room type does not belong to your assigned hotel.")

    item = amenity_service.create_amenity(db=db, amenity=amenity)
    return {"success": True, "message": "Amenity created successfully", "data": item}

@router.post("/bulk", response_model=ItemResponse[list[amenity_schema.AmenityItem]], status_code=status.HTTP_201_CREATED)
def create_amenities_bulk(
    bulk_data: amenity_schema.BulkAmenityCreate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Bulk create multiple amenities under a hotel or room type using JSON.
    Auto-resolves owner's or manager's hotel_id when omitted.
    """
    if not bulk_data.hotel_id and not bulk_data.room_type_id:
        bulk_data.hotel_id = resolve_and_verify_hotel_id(db, current_user, None)
    elif bulk_data.hotel_id:
        bulk_data.hotel_id = resolve_and_verify_hotel_id(db, current_user, bulk_data.hotel_id)
    elif bulk_data.room_type_id:
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
                raise HTTPException(status_code=403, detail="Access denied. The specified room type does not belong to your assigned hotel.")

    items = amenity_service.create_amenities_bulk(db=db, bulk_data=bulk_data)
    return {"success": True, "message": f"{len(items)} amenities created successfully", "data": items}

@router.get("", response_model=amenity_schema.AmenityPaginatedResponse)
def read_amenities(
    hotel_id: UUID | None = Query(default=None),
    room_type_id: UUID | None = Query(default=None),
    name: str | None = Query(default=None),
    name_op: StringFilterOperator | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: AmenitySortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    List amenities with advanced filtering and sorting.
    Auto-scopes to staff's hotel if logged in without explicit filters.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user")}
    if current_user and current_user.role and current_user.role.name.lower() in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
        if current_user.hotel_id:
            if not hotel_id and not room_type_id:
                query_params["hotel_id"] = current_user.hotel_id
            elif hotel_id and hotel_id != current_user.hotel_id:
                raise HTTPException(status_code=403, detail="Access denied. You can only view amenities for your assigned hotel.")

    return amenity_service.get_amenities(db=db, query_params=query_params)

@router.get("/{id}", response_model=amenity_schema.AmenityItemResponse)
def amenity_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    item = amenity_service.get_amenity_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Amenity retrieved successfully", "data": item}

@router.put("/{id}", response_model=amenity_schema.AmenityItemResponse)
def update_amenity(
    id: UUID,
    update_data: Annotated[amenity_schema.AmenityUpdate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    _check_amenity_ownership(db, id, current_user)
    item = amenity_service.update_amenity(db, id, update_data)
    return {"success": True, "message": "Amenity updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_amenity(
    id: UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    _check_amenity_ownership(db, id, current_user)
    item = amenity_service.delete_amenity(db, id)
    return {"success": True, "message": "Amenity deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=amenity_schema.AmenityItemResponse)
def restore_amenity(
    id: UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Restore a soft-deleted amenity.
    """
    _check_amenity_ownership(db, id, current_user)
    item = amenity_service.restore_amenity(db, id)
    return {"success": True, "message": "Amenity restored successfully", "data": item}
