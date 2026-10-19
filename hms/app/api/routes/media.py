from typing import Annotated, Literal
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, status, Form, Request, Query
import uuid
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas import media as media_schema
from app.services import media_service


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


class MediaSortBy(str, Enum):
    is_primary = "is_primary"
router = APIRouter(prefix="/media", tags=["Media"])

@router.post("", response_model=media_schema.MediaListResponse, status_code=status.HTTP_201_CREATED)
def create_media(media: Annotated[media_schema.MediaCreate, Form()], db: Session = Depends(get_db)):
    return {"media": [media_service.create_media(db=db, media=media)]}

@router.post("/bulk", response_model=media_schema.MediaListResponse, status_code=status.HTTP_201_CREATED)
def create_media_bulk(bulk_data: media_schema.BulkMediaCreate, db: Session = Depends(get_db)):
    """
    Bulk upload/create multiple media items under a hotel or room type using JSON.
    """
    return {"media": media_service.create_media_bulk(db=db, bulk_data=bulk_data)}

@router.get("", response_model=media_schema.MediaListResponse)
def read_media(
    hotel_id: UUID | None = Query(default=None),
    room_type_id: UUID | None = Query(default=None),
    is_primary: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page for pagination"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted records in results"),
    sort_by: MediaSortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default="asc"),
    db: Session = Depends(get_db)
):
    """
    List media with advanced filtering and sorting.
    """

    query_params = {k: v for k, v in locals().items() if v is not None and k not in ("db", "request")}
    return media_service.get_media(db=db, query_params=query_params)

@router.get("/{id}", response_model=media_schema.MediaListResponse)
def media_by_id(
    id: uuid.UUID,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    db: Session = Depends(get_db)
):
    return {"media": [media_service.get_media_by_id(db, id, include_deleted=include_deleted)]}

@router.put("/{id}", response_model=media_schema.MediaListResponse)
def update_media(id: uuid.UUID, update_data: Annotated[media_schema.MediaUpdate, Form()], db: Session = Depends(get_db)):
    return {"media": [media_service.update_media(db, id, update_data)]}

@router.delete("/{id}", response_model=media_schema.MediaListResponse)
def delete_media(id: uuid.UUID, db: Session = Depends(get_db)):
    return {"media": [media_service.delete_media(db, id)]}

@router.post("/{id}/restore", response_model=media_schema.MediaListResponse)
def restore_media(id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Restore a soft-deleted media item.
    """
    return {"media": [media_service.restore_media(db, id)]}
