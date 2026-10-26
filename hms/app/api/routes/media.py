from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_manager, get_optional_current_user
from app.models.user import User
from app.models.media import Media
from app.models.room_type import RoomType
from app.models.hotel import Hotel
from app.core.roles import UserRole
from app.utils.scoping_utils import resolve_and_verify_hotel_id
from app.schemas import media as media_schema
from app.schemas.common import ItemResponse, ActionResponse, SortOrder
from app.services import media_service
from enum import Enum

class MediaSortBy(str, Enum):
    is_primary = "is_primary"

router = APIRouter(prefix="/media", tags=["Media"])

def _check_media_ownership(db: Session, media_id: UUID, current_user: User):
    role_name = current_user.role.name.lower() if current_user.role else ""
    if role_name == UserRole.ADMIN.value:
        return
    db_media = db.query(Media).filter(Media.id == media_id).first()
    if not db_media:
        raise HTTPException(status_code=404, detail="Media not found.")
    effective_hotel_id = db_media.hotel_id
    if not effective_hotel_id and db_media.room_type_id:
        rt = db.query(RoomType).filter(RoomType.id == db_media.room_type_id).first()
        effective_hotel_id = rt.hotel_id if rt else None

    if effective_hotel_id:
        hotel = db.query(Hotel).filter(Hotel.id == effective_hotel_id).first()
        if role_name == UserRole.OWNER.value:
            if hotel and hotel.owner_id != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied. You do not own the hotel for this media.")
        elif role_name in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
            if current_user.hotel_id and effective_hotel_id != current_user.hotel_id:
                raise HTTPException(status_code=403, detail="Access denied. You can only modify media for your assigned hotel.")

@router.post("", response_model=media_schema.MediaItemResponse, status_code=status.HTTP_201_CREATED)
def create_media(
    media: Annotated[media_schema.MediaCreate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Create a media item.
    - If hotel_id is omitted and room_type_id is not specified, auto-resolves owner's or manager's hotel_id.
    - If room_type_id is specified, verifies it belongs to the owner's or manager's hotel.
    """
    if not media.hotel_id and not media.room_type_id:
        media.hotel_id = resolve_and_verify_hotel_id(db, current_user, None)
    elif media.hotel_id:
        media.hotel_id = resolve_and_verify_hotel_id(db, current_user, media.hotel_id)
    elif media.room_type_id:
        rt = db.query(RoomType).filter(RoomType.id == media.room_type_id, RoomType.deleted_at.is_(None)).first()
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

    item = media_service.create_media(db=db, media=media)
    return {"success": True, "message": "Media created successfully", "data": item}

@router.post("/bulk", response_model=ItemResponse[list[media_schema.MediaItem]], status_code=status.HTTP_201_CREATED)
def create_media_bulk(
    bulk_data: media_schema.BulkMediaCreate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Bulk upload/create multiple media items under a hotel or room type using JSON.
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

    items = media_service.create_media_bulk(db=db, bulk_data=bulk_data)
    return {"success": True, "message": f"{len(items)} media items created successfully", "data": items}

@router.get("", response_model=media_schema.MediaPaginatedResponse)
def read_media(
    hotel_id: UUID | None = Query(default=None),
    room_type_id: UUID | None = Query(default=None),
    is_primary: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: MediaSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    List media with advanced filtering and sorting.
    Auto-scopes to staff's hotel if logged in without explicit filters.
    """
    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request", "current_user")}
    if current_user and current_user.role and current_user.role.name.lower() in [UserRole.MANAGER.value, UserRole.RECEPTIONIST.value]:
        if current_user.hotel_id:
            if not hotel_id and not room_type_id:
                query_params["hotel_id"] = current_user.hotel_id
            elif hotel_id and hotel_id != current_user.hotel_id:
                raise HTTPException(status_code=403, detail="Access denied. You can only view media for your assigned hotel.")

    return media_service.get_media(db=db, query_params=query_params)

@router.get("/{id}", response_model=media_schema.MediaItemResponse)
def media_by_id(
    id: UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    item = media_service.get_media_by_id(db, id, include_deleted=include_deleted)
    return {"success": True, "message": "Media retrieved successfully", "data": item}

@router.put("/{id}", response_model=media_schema.MediaItemResponse)
def update_media(
    id: UUID,
    update_data: Annotated[media_schema.MediaUpdate, Form()],
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    _check_media_ownership(db, id, current_user)
    item = media_service.update_media(db, id, update_data)
    return {"success": True, "message": "Media updated successfully", "data": item}

@router.delete("/{id}", response_model=ActionResponse)
def delete_media(
    id: UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    _check_media_ownership(db, id, current_user)
    item = media_service.delete_media(db, id)
    return {"success": True, "message": "Media deleted successfully", "data": {"id": item.id}}

@router.post("/{id}/restore", response_model=media_schema.MediaItemResponse)
def restore_media(
    id: UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Restore a soft-deleted media item.
    """
    _check_media_ownership(db, id, current_user)
    item = media_service.restore_media(db, id)
    return {"success": True, "message": "Media restored successfully", "data": item}
